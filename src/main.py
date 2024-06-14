from repository_data_scraper import RepositoryDataScraper
from git import Repo
import os


if __name__ == '__main__':
    # Navigate to project root
    os.chdir('..')

    path_to_data = os.path.join(os.getcwd(), 'data')
    path_to_repositories = os.path.join(os.getcwd(), 'repos')

    demo_repo = Repo(os.path.join(path_to_repositories, 'demo-repo'))
    # Set working dir inside repo
    os.chdir(os.path.join(path_to_repositories, 'demo-repo'))

    repo_scraper = RepositoryDataScraper(repository=demo_repo, sliding_window_size=2)
    repo_scraper.compute_file_commit_grams()
