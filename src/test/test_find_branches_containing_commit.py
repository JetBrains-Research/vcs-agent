import unittest
import os
from git import Repo
from src.repository_data_scraper import RepositoryDataScraper


class FindBranchesContainingCommitTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir('../..')
        path_to_repositories = os.path.join(os.getcwd(), 'repos')

        demo_repo = Repo(os.path.join(path_to_repositories, 'demo-repo'))
        os.chdir(os.path.join(path_to_repositories, 'demo-repo'))

        self.repository_data_scraper = RepositoryDataScraper(repository=demo_repo, sliding_window_size=2)

    def test_that_all_branches_are_found_for_every_commit(self):
        commits_with_branches = {'10a9669': ['master'],
                                 'aeeab81': ['master'],
                                 '464e494': ['compliance-doc2', 'master'],
                                 '6cd3cd8': ['master'],
                                 'aa744a5': ['master'],
                                 'cf99230': ['doc-style-experimentation', 'master'],
                                 'a16b469': ['doc-style-experimentation', 'master'],
                                 'a1bc309': ['doc-style-experimentation', 'master'],
                                 '7821ce3': ['document2'],
                                 'e7f94bf': ['document2', 'document2-bugfixes'],
                                 '52fc194': ['document2', 'document2-bugfixes'],
                                 '618b1cb': ['compliance-doc2', 'document2', 'master'],
                                 '533d06d': ['compliance-doc2', 'document2', 'document2-bugfixes', 'master'],
                                 '025e106': ['compliance-doc2', 'doc-style-experimentation', 'document2',
                                             'document2-bugfixes', 'master']}

        for commit in commits_with_branches:
            self.assertEqual(commits_with_branches[commit],
                             self.repository_data_scraper.find_branches_containing_commit(commit))


if __name__ == '__main__':
    unittest.main()
