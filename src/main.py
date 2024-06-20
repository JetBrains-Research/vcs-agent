from repository_data_scraper import RepositoryDataScraper
from git import Repo, GitCommandError
import os
import pandas as pd


if __name__ == '__main__':
    # Navigate to project root
    os.chdir('..')

    path_to_data = os.path.join(os.getcwd(), 'data')
    path_to_repositories = os.path.join(os.getcwd(), 'repos')

    # demo_repo = Repo(os.path.join(path_to_repositories, 'demo-repo'))
    # Set working dir inside repo

    python_repositories_metadata = pd.read_csv(os.path.join(path_to_data, 'python_repos.csv'))
    for _, repository_metadata in python_repositories_metadata.iloc[1:2].iterrows():
        repository_path = os.path.join(path_to_repositories, "__".join(repository_metadata["name"].split("/")))
        try:
            repo_instance = Repo.clone_from(f'https://github.com/{repository_metadata["name"]}.git',
                                        f'{repository_path}')
        except GitCommandError as e:
            # If already exists, create Repo instance of it
            if 'already exists' in e.stderr:
                print('Repository already exists, using local directory instead of cloning.')
                repo_instance = Repo(repository_path)
            else:
                raise e

        os.chdir(os.path.join(path_to_data, repository_path))
    #os.chdir(os.path.join(path_to_repositories, 'demo-repo'))

        repo_scraper = RepositoryDataScraper(repository=repo_instance, sliding_window_size=2)
        repo_scraper.compute_file_commit_grams()

        print(f'Stats for repository {repository_metadata["name"]}:\n'
              f'Branches: {repository_metadata['branches']}\n'
              f'Merges: {repo_scraper.n_merge_commits}\n'
              f'Merges with resolved conflict: {repo_scraper.n_merge_commits_with_resolved_conflicts}\n'
              f'Cherry-pick commits: {repo_scraper.n_cherry_pick_commits}\n\n')
