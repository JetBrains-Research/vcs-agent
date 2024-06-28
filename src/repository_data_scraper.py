from git import Repo, Commit, NULL_TREE
import re
from queue import Queue
from tqdm import tqdm
from src.programming_language import ProgrammingLanguage
import hashlib
import time

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

    # Counters for specific commit types
    n_merge_commits = 0
    n_cherry_pick_commits = 0
    n_merge_commits_with_resolved_conflicts = 0
    programming_language = None

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

    def update_accumulator_with_file_commit_gram_scenario(self, file_state: dict, file_to_remove: str, branch: str):
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
                # meaning we visited the this branch origin's commit thus all commits thereafter
                if commit.hexsha not in self.visited_commits:
                    self.visited_commits.add(commit.hexsha)
                    self.__update_commit_message_tracker(commit)
                    frontier = self.__update_frontier_with(commit, frontier, is_merge_commit)
                elif keepalive > 0:
                    # If we hit a commit which we have already seen, it means we are hitting another branch
                    # To catch overlaps, we continue for keepalive commits
                    keepalive -= 1
                else:
                    # Now that we also handled overlaps, stop processing this branch
                    break

                if is_merge_commit:
                    self.n_merge_commits += 1
                    merge_commit_sample = {'merge_commit_hash': commit.hexsha, 'had_conflicts': False,
                                           'parents': [parent.hexsha for parent in commit.parents]}

                # Cherry-pick commits
                # re.compile(r'(cherry pick[ed]*|cherry-pick[ed]*|cherrypick[ed]*)')
                # Captures exactly the message appened to the cherry pick commit message by using the
                weak_cherry_pick_indicator = re.compile(r'(cherry pick[ed]*|cherry-pick[ed]*|cherrypick[ed]*)')
                if weak_cherry_pick_indicator.search(commit.message):
                    self.n_cherry_pick_commits += 1

                # -x option in git cherry-pick. Sadly this is no longer the default.
                cherry_pick_pattern = re.compile(r'(?<=cherry picked from commit )[a-z0-9]{40}')
                potential_cherry_pick_match = cherry_pick_pattern.search(commit.message)
                if potential_cherry_pick_match:
                    self.accumulator['cherry_pick_scenarios'].append({
                        'cherry_pick_commit': commit.hexsha,
                        'cherry_commit': potential_cherry_pick_match[0],
                        'parents': [parent.hexsha for parent in commit.parents]
                    })

                changes_in_commit = self.repository.git.show(commit, name_status=True, format='oneline').split('\n')
                changes_in_commit = changes_in_commit[1:]  # remove commit hash and message
                changes_in_commit = [change for change in changes_in_commit if change]  # filter empty lines

                # If any change in this commit is a valid change, we want to update the state
                # This is needed for the cleanup phase that removes stale files. Implicitly ensures that
                # len(changes_in_commit) > 0, because in this case should_process_commit remains False
                should_process_commit = False
                for change in changes_in_commit:
                    # Change types such as rename yield a list of length 3 here, cannot simply unpack in every case
                    change_type = change.split('\t')[0]
                    should_process_commit = change_type in valid_change_types
                    if should_process_commit:
                        break

                if should_process_commit:
                    # Commit has changes
                    affected_files = []

                    # Parse changes
                    # Do we need to update the state of this particular file?
                    for change_in_commit in changes_in_commit:
                        changes_to_unpack = change_in_commit.split('\t')
                        # Some changes in the commit might not be of a supported change type
                        if changes_to_unpack[0] not in valid_change_types:
                            continue

                        # Only maintain a state for files of required programming_language
                        change_type, file = changes_to_unpack
                        if self.programming_language.value not in file:
                            continue

                        affected_files.append(file)

                        if is_merge_commit and change_type == 'MM':
                            self.n_merge_commits_with_resolved_conflicts += 1
                            merge_commit_sample['had_conflicts'] = True

                        # Update the file state for every branch with this commit
                        # Otherwise ignore this commit (dont update state)
                        # We should maintain a state for this branch, ensure that we are
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

                        # We updated (Add, Update) one file of the commit for all affected branches at this point
                    # (Add, Update) ALL files of the commit for all affected branches
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

                if is_merge_commit:
                    self.accumulator['merge_scenarios'].append(merge_commit_sample)

            # After we are done with all commits, the state might contain valid commits if we have a
            # file commit-gram lasting until the last commit (ie we have just seen the file and then terminate)
            # To capture this edge case we need to iterate over the state one more time.
            for tracked_branch in self.state:
                for file in self.state[tracked_branch]:
                    if self.state[tracked_branch][file]['times_seen_consecutively'] >= self.sliding_window_size:
                        self.update_accumulator_with_file_commit_gram_scenario(self.state[tracked_branch][file], file,
                                                                               tracked_branch)

            # Clean up
            self.state = {}

        start = time.time()
        self.accumulator['cherry_pick_scenarios'] += self.mine_commits_with_duplicate_messages_for_cherry_pick_scenarios()
        print(f'Extra time incurred: {time.time() - start}s')

    def __update_frontier_with(self, commit, frontier, is_merge_commit):
        if is_merge_commit:
            for parent in commit.parents:
                # Ensure we continue on any path that is left available
                # If the FIFO causes problems, I can also use weighting with a prio queue and len(parents)
                if parent.hexsha not in self.visited_commits:
                    frontier.put(parent)
        elif len(commit.parents) == 1:
            frontier.put(commit.parents[0])

        return frontier

    def __update_commit_message_tracker(self, commit):
        if commit.message in self.seen_commit_messages:
            self.seen_commit_messages[commit.message].append(commit)
        else:
            self.seen_commit_messages.update({commit.message: [commit]})

    def mine_commits_with_duplicate_messages_for_cherry_pick_scenarios(self):
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
                    if self.do_patch_ids_match(pivot_commit, comparison_target):
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
        print(f'Found {len(additional_cherry_pick_scenarios)} additional cherry pick scenarios.')
        return additional_cherry_pick_scenarios

    def do_patch_ids_match(self, commit1: Commit, commit2: Commit) -> bool:
        # Generate the diff for the commit
        sha1 = self.generate_hash_from_patch(commit1)
        sha2 = self.generate_hash_from_patch(commit2)

        return sha1 == sha2

    def generate_hash_from_patch(self, commit: Commit) -> str:
        diff = commit.diff(other=commit.parents[0] if commit.parents else NULL_TREE, create_patch=True)
        try:
            diff_content = ''.join(d.diff.decode('utf-8') for d in diff)
        except UnicodeDecodeError:
            return ''

        # Normalize the patch
        normalized_diff = re.sub(r'^(index|diff|---|\+\+\+) .*\n', '', diff_content, flags=re.MULTILINE)
        normalized_diff = re.sub(r'^\s*\n', '', normalized_diff, flags=re.MULTILINE)

        return hashlib.sha1(normalized_diff.encode('utf-8')).hexdigest()
