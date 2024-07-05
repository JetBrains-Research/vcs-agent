from repository_data_scraper import RepositoryDataScraper
from git import Repo, GitCommandError
import os
import pandas as pd
from programming_language import ProgrammingLanguage

if __name__ == '__main__':
    # Navigate to project root
    os.chdir('..')

    path_to_data = os.path.join(os.getcwd(), 'data')
    path_to_repositories = os.path.join(os.getcwd(), 'repos')

    # repo_instance = Repo(os.path.join(path_to_repositories, 'demo-repo'))
    # Set working dir inside repo

    python_repositories_metadata = pd.read_csv(os.path.join(path_to_data, 'python_repos.csv'))
    repo_instance = None
    payload = None
    for i, repository_metadata in python_repositories_metadata.iloc[15:30].iterrows():
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
        # os.chdir(os.path.join(path_to_repositories, 'demo-repo'))

        repo_scraper = RepositoryDataScraper(repository=repo_instance, programming_language=ProgrammingLanguage.PYTHON,
                                             sliding_window_size=4)
        repo_scraper.scrape()

        repository_metadata['scraped_data'] = repo_scraper.accumulator
        repository_metadata['n_merge_scenarios'] = len(repo_scraper.accumulator['merge_scenarios'])
        repository_metadata['n_cherry_pick_scenarios'] = len(repo_scraper.accumulator['cherry_pick_scenarios'])
        repository_metadata['n_merge_scenarios_with_resolved_conflicts'] = len(
            [item for item in repo_scraper.accumulator['merge_scenarios'] if item['had_conflicts']]
        )

        if payload is None:
            payload = pd.DataFrame(columns=repository_metadata.index)
        payload.loc[i] = repository_metadata

        print(f'Stats for repository {repository_metadata["name"]}:\n'
              f'Branches: {repository_metadata['branches']}\n'
              f'Merge scenarios: {repository_metadata['n_merge_scenarios']}\n'
              f'Merge scenarios with resolved conflict: {repository_metadata['n_merge_scenarios_with_resolved_conflicts']}\n'
              f'Cherry-pick scenarios: {repository_metadata['n_cherry_pick_scenarios']}\n\n')
    payload.to_parquet(os.path.join(path_to_data, 'payload.parquet'), engine='pyarrow')
