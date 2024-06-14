from git import Repo, GitCommandError
import pandas as pd
import re


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

    # Counters for specific commit types
    n_merge_commits = 0
    n_cherry_pick_commits = 0
    n_merge_commits_with_resolved_conflicts = 0

    def __init__(self, repository: Repo, sliding_window_size: int = 3):
        if repository is None:
            raise ValueError("Please provide a repository instance to scrape from.")

        self.repository = repository
        self.sliding_window_size = sliding_window_size
        self.accumulator = []
        self.state = {}
        self.setup_branches()

    def setup_branches(self):
        branches = pd.Series(self.repository.git.branch('-a').split('\n'), name='branch_names')

        # Branches will initially just be remote, to check them out and pull them we clean them by removing:
        #   the remote prefix
        #   any whitespace
        #   literal line breaks
        #   the asterisk denoting the current branch
        branches = branches.str.replace(r'(remotes/origin/|\s*|\n|\*)', '', regex=True)

        # Then we remove the branch pointed at by the head (this is just METADATA and the branch would be duplicated
        # otherwise) E.g. HEAD->master and master, we want to keep master
        branches = branches[~branches.str.contains('HEAD->')]

        # Ensure that commits on remote branches become locally available in GitPython
        for branch in branches:
            self.repository.git.checkout(branch)

    def find_branches_containing_commit(self, commit_sha):
        # Find branches containing the commit
        branches_containing_commit = []
        for branch in self.repository.branches:
            branch_commit = self.repository.commit(branch)
            try:
                # Check if commit is reachable from the branch
                # Not sure if this is even correct
                # Ancestor is towards newer commits
                if self.repository.is_ancestor(commit_sha, branch_commit):
                    branches_containing_commit.append(branch.name)
            except GitCommandError as e:
                print(f"Error while processing branch {branch}: {e}")
                continue

        return branches_containing_commit

    def update_accumulator_with(self, file_state: dict, file_to_remove: str, branch: str):
        if file_state['times_seen_consecutively'] >= self.sliding_window_size:
            self.accumulator.append(
                {'file': file_to_remove, 'branch': branch, 'first_commit': file_state['first_commit'],
                 'last_commit': file_state['last_commit'],
                 'times_seen_consecutively': file_state['times_seen_consecutively']})

    def compute_file_commit_grams(self):
        valid_change_types = ['A', 'M', 'MM']
        for commit in self.repository.iter_commits(all=True, topo_order=True):  # We will visit each commit exactly once

            is_merge_commit = False
            # Demo repo ground truth = 3
            # Merge commits
            if len(commit.parents) > 1:
                self.n_merge_commits += 1
                is_merge_commit = True

            # Cherry-pick commits
            cherry_pick_pattern = re.compile(r'(cherry pick[ed]*|cherry-pick[ed]*|cherrypick[ed]*)')
            if cherry_pick_pattern.search(commit.message):
                self.n_cherry_pick_commits += 1

            branches_with_commit = self.find_branches_containing_commit(commit.hexsha)

            changes_in_commit = self.repository.git.show(commit, name_status=True, format='oneline').split('\n')
            changes_in_commit = changes_in_commit[1:]  # remove commit hash and message
            changes_in_commit = [change for change in changes_in_commit if change]  # filter empty lines

            # If any change in this commit is a valid change, we want to update the state
            # This is important, because operations on the state, when we dont want to perform them
            # can lead to flaky behaviour. This is needed for the cleanup phase that removes stale files.
            # Implicitly ensures that we len(changes_in_commit) > 0, because otherwise we would not iterate at all
            should_process_commit = False
            for change in changes_in_commit:
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
                    if changes_to_unpack[0] not in valid_change_types:
                        continue

                    change_type, file = changes_to_unpack
                    affected_files.append(file)

                    if is_merge_commit and change_type == 'MM':
                        self.n_merge_commits_with_resolved_conflicts += 1

                    # Update the file state for every branch with this commit
                    # Otherwise ignore this commit (dont update state)
                    for branch in branches_with_commit:
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
                for branch in branches_with_commit:
                    # Only do this for branches affected by the commit
                    new_state = {}
                    for file in self.state[branch]:
                        if file in affected_files:
                            new_state[file] = self.state[branch][file]
                        else:
                            self.update_accumulator_with(self.state[branch][file], file, branch)

                    self.state[branch] = new_state

        # After we are done with all commits, the state might contain valid commits if we have a
        # file commit-gram lasting until the last commit (ie we have just seen the file and then terminate)
        # To capture this edge case we need to iterate over the state one more time.
        for branch in self.state:
            for file in self.state[branch]:
                if self.state[branch][file]['times_seen_consecutively'] >= self.sliding_window_size:
                    self.update_accumulator_with(self.state[branch][file], file, branch)

        # Clean up
        self.state = None
