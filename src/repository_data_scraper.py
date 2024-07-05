from git import Repo, Commit, NULL_TREE
import re
from queue import Queue
from tqdm import tqdm
from src.programming_language import ProgrammingLanguage
import hashlib
import time
from typing import List

class RepositoryDataScraper:
    repository = None
    sliding_window_size = 3

    # Accumulates file-commit grams If we detect a series of n consecutive modifications of the same file we append a
    # dict to this list. Each dict contains: The associated file (relative path from working directory), first commit
    # for this file-commit gram, last commit for this file-commit gram and how many times the file was seen
    # consecutively (length of the file-commit gram) Note that the change_types that are valid are M, MM, A or R. All
    # other change types are ignored (because the file wasn't modified).
    accumulator = None

    # Maintains a state for each file currently in scope. Each scope is defined by the overlap size n, if we do not
    # see the file again after n steps we remove it from the state
    state = None

    visited_commits = None
    seen_commit_messages = None

    programming_language = None

    _cherry_pick_pattern = None

    def __init__(self, repository: Repo, programming_language: ProgrammingLanguage, sliding_window_size: int = 3):
        if repository is None:
            raise ValueError("Please provide a repository instance to scrape from.")

        self.repository = repository
        self.sliding_window_size = sliding_window_size
        self.programming_language = programming_language

        self.accumulator = {'file_commit_gram_scenarios': [], 'merge_scenarios': [], 'cherry_pick_scenarios': []}
        self.state = {}
        self.branches = [b.name for b in self.repository.references if 'HEAD' not in b.name]

        self.visited_commits = set()
        self.seen_commit_messages = dict()

        # Based on the string appended to the commit message by the -x option in git cherry-pick
        self._cherry_pick_pattern = re.compile(r'(?<=cherry picked from commit )[a-z0-9]{40}')

    def update_accumulator_with_file_commit_gram_scenario(self, file_state: dict, file_to_remove: str, branch: str):
        """
        Updates the accumulator with the state at the given branch and file_to_remove with a file-commit gram scenario
        if the scenario at branch and file_to_remove is >= self.sliding_window_size long.

        Args:
            file_state: (dict): A dictionary containing the state of the file.
            file_to_remove (str): The name of the file to be removed.
            branch (str): The name of the branch where the file exists.
        """
        if file_state['times_seen_consecutively'] >= self.sliding_window_size:
            self.accumulator['file_commit_gram_scenarios'].append(
                {'file': file_to_remove, 'branch': branch, 'first_commit': file_state['first_commit'],
                 'last_commit': file_state['last_commit'],
                 'times_seen_consecutively': file_state['times_seen_consecutively']})

    def scrape(self):
        valid_change_types = ['A', 'M', 'MM']
        for branch in tqdm(self.branches, desc=f'Parsing branches ...'):
            commit = self.repository.commit(branch)

            frontier = Queue(maxsize=0)
            frontier.put(commit)

            # If we hit a commit that was already covered by another branch, continue for
            # self.sliding_window_size - 1 commits to cover file-commit grams overlapping, with at least one
            # commit on the current branch
            keepalive = self.sliding_window_size - 1

            while not frontier.empty():
                commit = frontier.get()
                is_merge_commit = len(commit.parents) > 1
                merge_commit_sample = {}

                # Ensure we early stop if we run into a visited commit
                # This happens whenever this branch (the one currently being processed) joins another branch at
                # its branch origin, iff we have already processed  a branch running past this branch's origin,
                # meaning we visited this branch origin's commit thus all commits thereafter
                if commit.hexsha not in self.visited_commits:
                    self.visited_commits.add(commit.hexsha)
                    self._update_commit_message_tracker(commit)
                    frontier = self._update_frontier_with(commit, frontier, is_merge_commit)
                elif keepalive > 0:
                    # If we hit a commit which we have already seen, it means we are hitting another branch
                    # To catch overlaps, we continue for keepalive commits
                    keepalive -= 1
                else:
                    # Now that we also handled overlaps, stop processing this branch
                    break

                if is_merge_commit:
                    merge_commit_sample = {'merge_commit_hash': commit.hexsha, 'had_conflicts': False,
                                           'parents': [parent.hexsha for parent in commit.parents]}

                self._process_cherry_pick_scenario(commit)

                changes_in_commit = self._get_changes_in_commit(commit)

                if self._should_process_commit(changes_in_commit, valid_change_types):
                    affected_files = []

                    for change_in_commit in changes_in_commit:
                        changes_to_unpack = change_in_commit.split('\t')

                        # Only process valid change_types
                        if changes_to_unpack[0] not in valid_change_types:
                            continue

                        # Only maintain a state for files of required programming_language
                        change_type, file = changes_to_unpack
                        if self.programming_language.value not in file:
                            continue

                        affected_files.append(file)

                        if is_merge_commit and change_type == 'MM':
                            merge_commit_sample['had_conflicts'] = True

                        self._maintain_state_for_change_in_commit(branch, commit, file)
                    self._remove_stale_file_states(affected_files, branch)

                if is_merge_commit:
                    self.accumulator['merge_scenarios'].append(merge_commit_sample)

            self._handle_last_commit_file_commit_gram_edge_case()

            # Clean up
            self.state = {}

        start = time.time()
        self.accumulator[
            'cherry_pick_scenarios'] += self._mine_commits_with_duplicate_messages_for_cherry_pick_scenarios()
        print(f'Extra time incurred: {time.time() - start}s')

    def _handle_last_commit_file_commit_gram_edge_case(self):
        """
        Handle the edge case where file-commit grams are still active, or continuing in the last commit. In this case we
        need to also update the accumulator with these scenarios to successfully mine them.

        After we are done with all commits, the state might contain valid file-commit grams
        lasting until and including the last commit (ie we have just seen the file and then terminate).
        To capture this edge case we need to iterate over the state one more time.
        """
        for tracked_branch in self.state:
            for file in self.state[tracked_branch]:
                self.update_accumulator_with_file_commit_gram_scenario(self.state[tracked_branch][file], file,
                                                                       tracked_branch)

    def _remove_stale_file_states(self, affected_files: List[str], branch: str):
        """
        Removes stale file states from the state of the given branch.

        Some file-commit grams might have stopped in this commit. If this is the case, we no longer need to maintain
        a state for them. If their length was >= self.sliding_window_size we should successfully mined a scenario
        and must update the accumulator with it.

        Args:
            affected_files (List[str]): List of files affected by the commit.
            branch (str): Branch affected by the commit.

        """
        # Now we only need to remove stale file states (files that were not found in the commit)
        # Only do this for branches affected by the commit
        if self.state:
            new_state = {}
            for file in self.state[branch]:
                if file in affected_files:
                    new_state[file] = self.state[branch][file]
                else:
                    self.update_accumulator_with_file_commit_gram_scenario(self.state[branch][file], file,
                                                                           branch)
            self.state[branch] = new_state

    def _maintain_state_for_change_in_commit(self, branch: str, commit: Commit, file: str):
        """
        Updates the state. Does not write any results to the accumulator.

        Initializes the state for a branch with a empty dict if we are not currently maintaining
        a state for this branch. Then keeps track of file-commit grams >= self.sliding_window_size

        Args:
            branch (str): The name of the branch where the commit occurred.
            commit (Commit): The Commit object representing the commit being made.
            file (str): The name of the file that was changed in the commit.

        """
        if branch not in self.state:
            self.state[branch] = {}

        if file in self.state[branch]:
            # We are maintaining a state for this file on this branch
            self.state[branch][file]['times_seen_consecutively'] = self.state[branch][file][
                                                                       'times_seen_consecutively'] + 1

            if self.state[branch][file]['times_seen_consecutively'] >= self.sliding_window_size:
                self.state[branch][file]['last_commit'] = commit.hexsha
        else:
            # We are not currently maintaining a state for this file in this branch, but have
            # detected it Need to set up the state dict
            self.state[branch][file] = {'first_commit': commit.hexsha, 'last_commit': commit.hexsha,
                                        'times_seen_consecutively': 1}

    def _should_process_commit(self, changes_in_commit, valid_change_types) -> bool:
        """
        Processes changes in commit to determine if any change is of a valid change type.

        Implicitly ensures that len(changes_in_commit) > 0, because in this case should_process_commit remains False

        Args:
            changes_in_commit: A list of changes in the commit.
            valid_change_types: A list of valid change types.

        Returns:
            bool: True if any change in the commit is a valid change type, False otherwise.
        """
        #
        should_process_commit = False
        for change in changes_in_commit:
            # Change types such as rename yield a list of length 3 here, cannot simply unpack in every case
            change_type = change.split('\t')[0]
            should_process_commit = change_type in valid_change_types
            if should_process_commit:
                return should_process_commit
        return should_process_commit

    def _get_changes_in_commit(self, commit: Commit) -> List:
        """
        Generates a list of changes in a commit using git show with arguments: name_status=True, format='oneline'.
        Contains only actual changes. Changes start with a change type followed by the affected file(s).
        Can affect multiple files for e.g. renaming.

        Args:
            commit (Commit): The commit object representing the commit for which changes are to be retrieved.

        Returns:
            List: A list of strings representing the changes in the given commit.
        """
        changes_in_commit = self.repository.git.show(commit, name_status=True, format='oneline').split('\n')
        changes_in_commit = changes_in_commit[1:]  # remove commit hash and message
        changes_in_commit = [change for change in changes_in_commit if change]  # filter empty lines
        return changes_in_commit

    def _process_cherry_pick_scenario(self, commit: Commit):
        """
        Checks the commit message for a cherry-pick scenario and, if present, adds it to the class's accumulator.

        This function does not return a value. Instead, it updates the class's accumulator with the following
             data structure:
            {
                'cherry_pick_commit': <commit hash (str)>,
                'cherry_commit': <matched cherry-pick commit (str)>,
                'parents': <list of parent hashes (list[str])>
            }

        Args:
            commit (Commit): A commit object to be checked for a cherry-pick scenario.
        """
        potential_cherry_pick_match = self._cherry_pick_pattern.search(commit.message)
        if potential_cherry_pick_match:
            self.accumulator['cherry_pick_scenarios'].append({
                'cherry_pick_commit': commit.hexsha,
                'cherry_commit': potential_cherry_pick_match[0],
                'parents': [parent.hexsha for parent in commit.parents]
            })

    def _update_frontier_with(self, commit: Commit, frontier: Queue, is_merge_commit: bool):
        """
        Adds the commit's parents to the frontier and returns the frontier.

        Args:
            commit (Commit): The commit object to update the frontier with.
            frontier (Queue): The queue containing the commits to be processed.
            is_merge_commit (bool): A boolean indicating whether the given commit is a merge commit.

        Returns:
            frontier (Queue): The updated queue containing the commits to be processed.
        """
        if is_merge_commit:
            for parent in commit.parents:
                # Ensure we continue on any path that is left available
                if parent.hexsha not in self.visited_commits:
                    frontier.put(parent)
        elif len(commit.parents) == 1:
            frontier.put(commit.parents[0])

        return frontier

    def _update_commit_message_tracker(self, commit: Commit):
        """
        If a new commit message is detected, adds a new dict element, otherwise appends the commit to the
        list at `commit.message`.

        Args:
            commit (Commit): The commit to update the commit message tracker with.
        """
        if commit.message in self.seen_commit_messages:
            self.seen_commit_messages[commit.message].append(commit)
        else:
            self.seen_commit_messages.update({commit.message: [commit]})

    def _mine_commits_with_duplicate_messages_for_cherry_pick_scenarios(self):
        duplicate_messages = [{k: v} for k, v in self.seen_commit_messages.items() if len(v) > 1]

        if len(duplicate_messages) == 0:
            return []

        additional_cherry_pick_scenarios = []

        # We could have n > 1 commits of a message, pairwise computation is costly
        for duplicate_message in duplicate_messages:
            commits = next(iter(duplicate_message.values()))
            for i, pivot_commit in enumerate(commits):
                comparison_targets = commits[i + 1:]  # Only process triangular sub-matrix without diagonal
                for comparison_target in comparison_targets:
                    if self._do_patch_ids_match(pivot_commit, comparison_target):
                        if pivot_commit.committed_datetime < comparison_target.committed_datetime:
                            additional_cherry_pick_scenarios.append({
                                'cherry_pick_commit': comparison_target.hexsha,
                                'cherry_commit': pivot_commit.hexsha,
                                'parents': [parent.hexsha for parent in comparison_target.parents]
                            })
                        elif pivot_commit.committed_datetime > comparison_target.committed_datetime:
                            additional_cherry_pick_scenarios.append({
                                'cherry_pick_commit': pivot_commit.hexsha,
                                'cherry_commit': comparison_target.hexsha,
                                'parents': [parent.hexsha for parent in pivot_commit.parents]
                            })
            # Timeout mechanism to avoid collecting excessive amounts of scenarios from a single repository
            if len(additional_cherry_pick_scenarios) >= 50:
                print(f'Early stopping mining for additional cherry-pick scenarios, because 50 were already found.'
                      f'Skipping {additional_cherry_pick_scenarios} scenario remaining candidates would have been')
                break
        print(f'Found {len(additional_cherry_pick_scenarios)} additional cherry pick scenarios.')
        return additional_cherry_pick_scenarios

    def _do_patch_ids_match(self, commit1: Commit, commit2: Commit) -> bool:
        # Generate the diff for the commit
        sha1 = self._generate_hash_from_patch(commit1)
        sha2 = self._generate_hash_from_patch(commit2)

        return sha1 == sha2

    def _generate_hash_from_patch(self, commit: Commit) -> str:
        diff = commit.diff(other=commit.parents[0] if commit.parents else NULL_TREE, create_patch=True)
        try:
            diff_content = ''.join(d.diff.decode('utf-8') for d in diff)
        except UnicodeDecodeError:
            return ''

        # Normalize the patch
        normalized_diff = re.sub(r'^(index|diff|---|\+\+\+) .*\n', '', diff_content, flags=re.MULTILINE)
        normalized_diff = re.sub(r'^\s*\n', '', normalized_diff, flags=re.MULTILINE)

        return hashlib.sha1(normalized_diff.encode('utf-8')).hexdigest()
