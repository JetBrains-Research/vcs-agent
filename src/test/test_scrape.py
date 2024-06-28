import unittest
import os
from git import Repo
from src.repository_data_scraper import RepositoryDataScraper
from src.programming_language import ProgrammingLanguage


class ScrapeTestCase(unittest.TestCase):
    def test_should_generate_target_file_commit_grams(self):
        os.chdir('../..')
        path_to_repositories = os.path.join(os.getcwd(), 'repos')

        demo_repo = Repo(os.path.join(path_to_repositories, 'demo-repo'))
        os.chdir(os.path.join(path_to_repositories, 'demo-repo'))

        self.repository_data_scraper = RepositoryDataScraper(repository=demo_repo,
                                                             programming_language=ProgrammingLanguage.TEXT,
                                                             sliding_window_size=2)

        target_file_commit_grams = [{
            'file': 'document2.txt',
            'branch': 'compliance-doc2',
            'first_commit': '464e49457108e9685e0634c9da87254a85c06c07',
            'last_commit': '533d06d3173710a8d1cb15b823cb7f9dcf72d536',
            'times_seen_consecutively': 3},
            {'file': 'document2.txt',
             'branch': 'master',
             'first_commit': 'aeeab817a1bd7d146fc7596546e0c98a0ec94dbc',
             'last_commit': '6cd3cd82bfa90b80e9435513a06014ec898de4a2',
             'times_seen_consecutively': 2},
            {'file': 'document.txt',
             'branch': 'doc-style-experimentation',
             'first_commit': 'cf99230146d4be91004b0a68c17c69ce65945ad2',
             'last_commit': '025e1062182f5ecb404767c17180310923b0f134',
             'times_seen_consecutively': 4},
            {'file': 'document2.txt',
             'branch': 'document2',
             'first_commit': '7821ce308f797eeec65da787b96c829238e15d11',
             'last_commit': '533d06d3173710a8d1cb15b823cb7f9dcf72d536',
             'times_seen_consecutively': 4}]

        self.repository_data_scraper.scrape()
        candidate_file_commit_grams = self.repository_data_scraper.accumulator['file_commit_gram_scenarios']

        self.assertEqual(len(candidate_file_commit_grams), len(target_file_commit_grams))

        for candidate_file_commit_gram in candidate_file_commit_grams:
            self.assertIn(candidate_file_commit_gram, target_file_commit_grams)

    def test_accumulator_should_not_contain_grams_of_invalid_file_type(self):
        os.chdir('../..')
        path_to_repositories = os.path.join(os.getcwd(), 'repos')

        demo_repo = Repo(os.path.join(path_to_repositories, 'mixed-file-types-demo'))
        os.chdir(os.path.join(path_to_repositories, 'mixed-file-types-demo'))

        # PYTHON should not contain TEXT grams
        self.repository_data_scraper = RepositoryDataScraper(repository=demo_repo,
                                                             programming_language=ProgrammingLanguage.PYTHON,
                                                             sliding_window_size=2)

        self.repository_data_scraper.scrape()
        candidate_file_commit_grams = self.repository_data_scraper.accumulator['file_commit_gram_scenarios']

        for candidate_file_commit_gram in candidate_file_commit_grams:
            self.assertTrue(
                self.repository_data_scraper.programming_language.value in candidate_file_commit_gram['file'])

        # TEXT should not contain PYTHON grams
        self.repository_data_scraper = RepositoryDataScraper(repository=demo_repo,
                                                             programming_language=ProgrammingLanguage.TEXT,
                                                             sliding_window_size=2)

        self.repository_data_scraper.scrape()
        candidate_file_commit_grams = self.repository_data_scraper.accumulator['file_commit_gram_scenarios']

        for candidate_file_commit_gram in candidate_file_commit_grams:
            self.assertTrue(
                self.repository_data_scraper.programming_language.value in candidate_file_commit_gram['file'])


if __name__ == '__main__':
    unittest.main()
