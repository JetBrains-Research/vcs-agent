from git import Repo, GitCommandError
import pandas as pd
import re

def is_merge_commit(commit):
    return len(commit.parents) > 1


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
        # Filter head out of branches to avoid duplicate state tracking
        #self.branches = [ref.name for ref in self.repository.refs if 'HEAD' not in ref.name]

    def update_accumulator_with(self, file_state: dict, file_to_remove: str, branch: str):
        if file_state['times_seen_consecutively'] >= self.sliding_window_size:
            self.accumulator.append(
                {'file': file_to_remove, 'branch': branch, 'first_commit': file_state['first_commit'],
                 'last_commit': file_state['last_commit'],
                 'times_seen_consecutively': file_state['times_seen_consecutively']})

    def scrape(self):
        valid_change_types = ['M', 'MM', 'A']
        for commit in self.repository.iter_commits(all=True, topo_order=True):

            is_merge_commit = self.does_commit_have_multiple_parents(commit)
            self.update_cherry_pick_commit_counter(commit)

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
                if is_merge_commit and change_type == 'MM':
                    self.n_merge_commits_with_resolved_conflicts += 1

    def update_cherry_pick_commit_counter(self, commit):
        cherry_pick_pattern = re.compile(r'(cherry pick[ed]*|cherry-pick[ed]*|cherrypick[ed]*)')
        if cherry_pick_pattern.search(commit.message):
            self.n_cherry_pick_commits += 1
