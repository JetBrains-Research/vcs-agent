from git import Repo, GitCommandError
import pandas as pd
from tqdm import tqdm
import re
import os

from programming_language import ProgrammingLanguage


def is_merge_commit(commit):
    return len(commit.parents) > 1


class RepositoryDataScraper:
    repository = None
    language_to_scrape_for: ProgrammingLanguage = None
    repository_path: str = None
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

    def __init__(self, repository: Repo, sliding_window_size: int = 3,
                 language_to_scrape_for: ProgrammingLanguage = None,
                 repository_path: str = None):
        if repository is None:
            raise ValueError("Please provide a repository instance to scrape from.")

        self.repository = repository
        self.sliding_window_size = sliding_window_size
        self.accumulator = []
        self.state = {}

        if language_to_scrape_for is None:
            raise ValueError("Please provide a language to scrape files for."
                             "File types cannot be filtered without this.")

        self.language_to_scrape_for = language_to_scrape_for

        if repository_path is None:
            raise ValueError("Please provide a repository path."
                             "It is not possible to determine file-commit grams without knowing the file locations.")

        self.repository_path = repository_path
        # Filter head out of branches to avoid duplicate state tracking
        #self.branches = [ref.name for ref in self.repository.refs if 'HEAD' not in ref.name]

    def update_accumulator_with(self, file_state: dict, file: str):
        self.accumulator.append(
            {'file': file, 'first_commit': file_state['first_commit'], 'last_commit': file_state['last_commit'],
             'times_seen_consecutively': file_state['times_seen_consecutively']})

    def scrape(self):
        commits = self.scrape_commit_based_metadata()
        self.scrape_file_commit_grams(commits)

    def scrape_file_commit_grams(self, commits: Dict):
        for directory, subdirs, files in os.walk(self.repository_path):
            if re.match(r'.*(\\|/)\..*', directory): # TODO this regex might not be 100% correct, complains abt escape sequence
                continue  # Skip hidden folders

            for file in files:
                if self.language_to_scrape_for.value not in file:
                    continue

                raw_blame = self.get_raw_git_blame_for(file)
                file_commit_history = self.parse(raw_blame)
                for i, commit_hash in enumerate(file_commit_history):
                    # Note: This traverses git rev-list until commit_hash
                    #   Could hinder performance if we access commits randomly
                    #   Store commits in Hashmap ie dict?
                    commit = commits[commit_hash]
                    parent_hashes = [parent.hexsha for parent in commit.parents]
                    if (i + 1) < (len(file_commit_history) - 1) and file_commit_history[i + 1] in parent_hashes:
                        # Next commit in file changelist is a parent -> Direct predecessor
                        # TODO How to deal with multiple file-commit grams per file change history
                        if self.state[file] is None:
                            self.state[file] = {'first_commit': file_commit_history[i + 1],
                                                'last_commit': file_commit_history[i + 1],
                                                'times_seen_consecutively': 1}
                        else:
                            self.state[file]['last_commit'] = file_commit_history[i + 1]
                            self.state[file]['times_seen_consecutively'] += 1
                    else:
                        # Subsequent changelist is broken
                        # Transfer to accumulator and reset state
                        if self.state[file]['times_seen_consecutively'] >= self.sliding_window_size:
                            self.update_accumulator_with(self.state[file], file)
                        self.state[file] = None

    def get_raw_git_blame_for(self, file):
        return self.repository.git.blame('--incremental', file)

    def parse(self, raw_blame):
        return [None]

    def scrape_commit_based_metadata(self):
        # NOTE: Took 3:21 min for 1 repo with 5k commits
        commits = {}
        for commit in self.repository.iter_commits(all=True, topo_order=True):
            commits.update({commit.hexsha: commit})

            if is_merge_commit(commit):
                self.n_merge_commits += 1
            self.update_cherry_pick_commit_counter(commit)

            changes_in_commit = self.repository.git.show(commit, name_status=True, format='oneline').split('\n')
            changes_in_commit = changes_in_commit[1:]  # remove commit hash and message
            changes_in_commit = [change for change in changes_in_commit if change]  # filter empty lines

            # If any change in this commit is a valid change, we want to update the state
            # This is important, because operations on the state, when we dont want to perform them
            # can lead to flaky behaviour. This is needed for the cleanup phase that removes stale files.
            # Implicitly ensures that we len(changes_in_commit) > 0, because otherwise we would not iterate at all
            for change in changes_in_commit:
                change_type = change.split('\t')[0]
                if is_merge_commit and change_type == 'MM':
                    self.n_merge_commits_with_resolved_conflicts += 1

        return commits

    def update_cherry_pick_commit_counter(self, commit):
        cherry_pick_pattern = re.compile(r'(cherry pick[ed]*|cherry-pick[ed]*|cherrypick[ed]*)')
        if cherry_pick_pattern.search(commit.message):
            self.n_cherry_pick_commits += 1
