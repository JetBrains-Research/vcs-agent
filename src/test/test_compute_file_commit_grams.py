import unittest
import os
from git import Repo
from src.repository_data_scraper import RepositoryDataScraper


class ComputeFileCommitGramsTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir('../..')
        path_to_repositories = os.path.join(os.getcwd(), 'repos')

        demo_repo = Repo(os.path.join(path_to_repositories, 'demo-repo'))
        os.chdir(os.path.join(path_to_repositories, 'demo-repo'))

        self.repository_data_scraper = RepositoryDataScraper(repository=demo_repo, sliding_window_size=2)

    def test_should_generate_target_file_commit_grams(self):
        target_file_commit_grams = [
            {'file': 'document2.txt', 'branch': 'master', 'first_commit': 'aeeab817a1bd7d146fc7596546e0c98a0ec94dbc',
             'last_commit': '6cd3cd82bfa90b80e9435513a06014ec898de4a2', 'times_seen_consecutively': 3},
            {'file': 'document.txt', 'branch': 'master', 'first_commit': 'cf99230146d4be91004b0a68c17c69ce65945ad2',
             'last_commit': 'a1bc309f890d0f20426859ec02c9fe4839c27559', 'times_seen_consecutively': 3},
            {'file': 'document2.txt', 'branch': 'compliance-doc2',
             'first_commit': '464e49457108e9685e0634c9da87254a85c06c07',
             'last_commit': '533d06d3173710a8d1cb15b823cb7f9dcf72d536', 'times_seen_consecutively': 3},
            {'file': 'document2.txt', 'branch': 'document2', 'first_commit': '7821ce308f797eeec65da787b96c829238e15d11',
             'last_commit': '533d06d3173710a8d1cb15b823cb7f9dcf72d536', 'times_seen_consecutively': 5},
            {'file': 'document2.txt', 'branch': 'document2-bugfixes',
             'first_commit': 'e7f94bfac56abc6a0b408fee81c018fd220030f0',
             'last_commit': '533d06d3173710a8d1cb15b823cb7f9dcf72d536', 'times_seen_consecutively': 3},
            {'file': 'document2.txt', 'branch': 'master', 'first_commit': '618b1cb31ac5069b193603e09e3147472166b663',
             'last_commit': '533d06d3173710a8d1cb15b823cb7f9dcf72d536', 'times_seen_consecutively': 2},
            {'file': 'document.txt', 'branch': 'doc-style-experimentation',
             'first_commit': 'cf99230146d4be91004b0a68c17c69ce65945ad2',
             'last_commit': '025e1062182f5ecb404767c17180310923b0f134', 'times_seen_consecutively': 4}]

        self.repository_data_scraper.compute_file_commit_grams()
        candidate_file_commit_grams = self.repository_data_scraper.accumulator

        self.assertEqual(len(candidate_file_commit_grams), len(target_file_commit_grams))

        for candidate_file_commit_gram in candidate_file_commit_grams:
            self.assertIn(candidate_file_commit_gram, target_file_commit_grams)


if __name__ == '__main__':
    unittest.main()
