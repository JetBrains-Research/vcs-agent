from repository_data_scraper import RepositoryDataScraper
from git import Repo, GitCommandError
import os
import pandas as pd
from programming_language import ProgrammingLanguage
from concurrent.futures import ProcessPoolExecutor, as_completed
import shutil, stat
import traceback


def scrape_repository(repository_metadata: pd.Series, path_to_repositories: str, path_to_data: str) -> pd.Series:
    """
    Scrapes a GitHub repository for data using the given repository metadata and file paths.

    Parameters:
    - repository_metadata (pd.Series): The metadata of the GitHub repository from SEART.
    - path_to_repositories (str): The path to the directory where repositories will be cloned or accessed.
    - path_to_data (str): The path to the directory where the scraped data will be saved.

    Returns:
    - repository_metadata (pd.Series): The updated metadata of the GitHub repository, including any errors encountered during scraping.
    """
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
            # Capture any unexpected error and store its traceback for debugging
            repository_metadata['error'] = traceback.format_exc()
            return repository_metadata

    os.chdir(os.path.join(path_to_data, repository_path))
    repo_scraper = RepositoryDataScraper(repository=repo_instance, programming_language=ProgrammingLanguage.PYTHON,
                                         sliding_window_size=3)  # Reduced sliding window size to 3
    try:
        repo_scraper.scrape()
        repository_metadata = update_repository_metadata_with_scraper_results(repo_scraper, repository_metadata)
    except Exception:
        # Capture any exception and store it for debugging
        repository_metadata['error'] = traceback.format_exc()
        return repository_metadata

    return repository_metadata


def update_repository_metadata_with_scraper_results(repo_scraper: RepositoryDataScraper, repository_metadata: pd.Series):
    """

    Update repository metadata with scraper results.

    This method updates the repository metadata dictionary with the results from the given repo_scraper.

    Parameters:
    - repo_scraper (RepositoryDataScraper): The scraper object containing the results to update the metadata with.
    - repository_metadata (pd.Series): The dictionary representing the repository metadata.

    Returns:
    - pd.Series: The updated repository metadata dictionary.

    """
    repository_metadata['scraped_data'] = repo_scraper.accumulator
    repository_metadata['n_merge_scenarios'] = len(repo_scraper.accumulator['merge_scenarios'])
    repository_metadata['n_cherry_pick_scenarios'] = len(repo_scraper.accumulator['cherry_pick_scenarios'])
    repository_metadata['n_merge_scenarios_with_resolved_conflicts'] = len(
        [item for item in repo_scraper.accumulator['merge_scenarios'] if item['had_conflicts']]
    )
    repository_metadata['n_file_commit_gram_scenarios'] = len(
        repo_scraper.accumulator['file_commit_gram_scenarios'])

    return repository_metadata


def on_rm_error(func, path, exc_info):
    """
    This method is called by the shutil.rmtree() function when it encounters an error while trying to remove a directory
     or a file. It is used to handle the error and continue with the removal operation.

    Parameters:
    - func: A function object that represents the removal function to be called again for the specific path.
        It should accept a single parameter, which is the path to be removed.
    - path: A string that represents the path of the directory or file that encountered the error.
    - exc_info: Unused by the implementation.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


if __name__ == '__main__':
    os.chdir('..')

    path_to_data = os.path.join(os.getcwd(), 'data')
    path_to_repositories = os.path.join(os.getcwd(), 'repos')

    repositories_metadata = pd.read_csv(os.path.join(path_to_data, 'python_repos.csv'))
    smaller_repositories_metadata = repositories_metadata[repositories_metadata['branches'] < 100].iloc[:6]
    results = []
    paths_to_directories_to_remove = []

    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(scrape_repository, repo, path_to_repositories, path_to_data)
                   for _, repo in smaller_repositories_metadata.iterrows()]
        for future in as_completed(futures):
            try:
                remaining_paths_to_directories_to_remove = []

                result = future.result()
                results.append(result)
                paths_to_directories_to_remove.append(os.path.join(path_to_repositories,
                                                                   "__".join(result["name"].split("/"))))
                print(f'\n\nScraped {len(results)} repos. {results[-1]['name']}', flush=True)

                # After every success attempt to clean up directory structure
                for path_to_directory in paths_to_directories_to_remove:
                    try:
                        shutil.rmtree(path_to_directory, onerror=on_rm_error)
                    except PermissionError:
                        remaining_paths_to_directories_to_remove.append(path_to_directory)
                        continue

                paths_to_directories_to_remove = remaining_paths_to_directories_to_remove
            except Exception as e:
                print(f'Exception occurred: {traceback.format_exc()}', flush=True)

    repositories_metadata = pd.concat(results, axis=1).T
    repositories_metadata.to_parquet(os.path.join(path_to_data, 'python_small_subset.parquet'), engine='pyarrow')

    # Clean up any remaining repositories created by the scraping process in the repository directory
    for path_to_directory in paths_to_directories_to_remove:
        try:
            shutil.rmtree(path_to_directory, onerror=on_rm_error)
        except PermissionError:
            continue
