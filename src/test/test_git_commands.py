import unittest
from unittest.mock import MagicMock

from src.ideformer_client.environment.evaluator import Evaluator
from src.ideformer_client.environment.scenario_type import ScenarioType

import os
import subprocess

class TestEvaluator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.evaluator = Evaluator(MagicMock(), 'branch_name', 'work_dir')

        os.chdir('../..')
        cls.path_to_repositories = os.path.join(os.getcwd(), 'repos', 'testing-repositories')

        os.chdir(os.path.join(cls.path_to_repositories, 'test-agent-patch-evaluation.git'))

    def test_agent_made_no_commits_and_head_is_at_last_commit(self):
        self.evaluator.set_scenario({'file': 'demo.py',
                                     'branch': 'main',
                                     'first_commit': 'bba5f390baad5f3e1506df4066f9e339ec88b490',
                                     'last_commit': 'bba5f390baad5f3e1506df4066f9e339ec88b490',
                                     'times_seen_consecutively': 3})
        self.evaluator.set_scenario_type(ScenarioType.FILE_COMMIT_GRAM_CHUNK)
        self.evaluator.agent_target_branch_name = 'test-same-head-as-last-commit'

        command = self.evaluator._get_git_file_commit_gram_evaluation_command()
        result = subprocess.run(command, capture_output=True, shell=True).stdout

        self.assertEqual(result.decode('utf-8').strip(), '0')

    def test_agent_made_commits_same_patch(self):
        self.evaluator.set_scenario({'file': 'demo.py',
                                     'branch': 'main',
                                     'first_commit': 'f238164291f0e57ab020e2372568ea048a794d5b',
                                     'last_commit': 'bba5f390baad5f3e1506df4066f9e339ec88b490',
                                     'times_seen_consecutively': 3})
        self.evaluator.set_scenario_type(ScenarioType.FILE_COMMIT_GRAM_CHUNK)
        self.evaluator.agent_target_branch_name = 'test-agent-made-commits-same-diff'

        command = self.evaluator._get_git_file_commit_gram_evaluation_command()
        result = subprocess.run(command, capture_output=True, shell=True).stdout

        # Patch matches (diff is empty), but the agent made 1 commit fewer
        self.assertEqual(result.decode('utf-8').strip(), '1')

    def test_agent_made_commits_different_patches(self):
        self.evaluator.set_scenario({'file': 'demo.py',
                                     'branch': 'main',
                                     'first_commit': 'f238164291f0e57ab020e2372568ea048a794d5b',
                                     'last_commit': 'bba5f390baad5f3e1506df4066f9e339ec88b490',
                                     'times_seen_consecutively': 3})
        self.evaluator.set_scenario_type(ScenarioType.FILE_COMMIT_GRAM_CHUNK)
        self.evaluator.agent_target_branch_name = 'test-agent-made-commits-divergent-diff'

        command = self.evaluator._get_git_file_commit_gram_evaluation_command()
        result = subprocess.run(command, capture_output=True, shell=True).stdout

        # Patches are different (non-empty diff)
        self.assertGreater(len(result.decode('utf-8').strip()), 1)

        self.assertNotEqual(result.decode('utf-8').strip(), '1')
