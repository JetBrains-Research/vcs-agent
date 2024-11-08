import unittest
from unittest.mock import MagicMock

from src.ideformer_client.environment.evaluator import Evaluator, ScenarioEnvironmentException
from src.ideformer_client.environment.scenario_type import ScenarioType


class TestEvaluator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.evaluator = Evaluator(MagicMock(), 'branch_name', 'work_dir')

    def test_evaluate_iteratively_chunk_staged_diff_into_commits_exception(self):
        self.evaluator.set_scenario({'file': 'library/src/main/java/com/tokenautocomplete/TokenCompleteTextView.kt',
                                   'branch': 'main',
                                   'first_commit': '1a862d94f57d30714732c5b5ca0537af4c7d91e7',
                                   'last_commit': '68e876ee5e055532a492a68b50dd5dd41dd474b6',

                                   'times_seen_consecutively': 7})
        self.evaluator.set_scenario_type(ScenarioType.FILE_COMMIT_GRAM_CHUNK)
        self.evaluator.container.exec_run = MagicMock(side_effect=lambda command_to_execute, privileged, workdir: (1, b'Error'))

        with self.assertRaises(ScenarioEnvironmentException):
            self.evaluator._evaluate_iteratively_chunk_staged_diff_into_commits()

    def test_evaluate_iteratively_chunk_staged_diff_into_commits_false(self):
        self.evaluator.set_scenario({'file': 'library/src/main/java/com/tokenautocomplete/TokenCompleteTextView.kt',
                                     'branch': 'main',
                                     'first_commit': '1a862d94f57d30714732c5b5ca0537af4c7d91e7',
                                     'last_commit': '68e876ee5e055532a492a68b50dd5dd41dd474b6',
                                     'times_seen_consecutively': 7})
        self.evaluator.set_scenario_type(ScenarioType.FILE_COMMIT_GRAM_CHUNK)

        output = b'1'
        self.evaluator.container.exec_run = MagicMock(return_value=(0, output))
        self.evaluator._can_be_cast_to_int = MagicMock(side_effect=lambda x: True)

        result = self.evaluator._evaluate_iteratively_chunk_staged_diff_into_commits()
        self.assertEqual(result, False)

    def test_evaluate_iteratively_chunk_staged_diff_into_commits_true(self):
        self.evaluator.set_scenario({'file': 'library/src/main/java/com/tokenautocomplete/TokenCompleteTextView.kt',
                                     'branch': 'main',
                                     'first_commit': '1a862d94f57d30714732c5b5ca0537af4c7d91e7',
                                     'last_commit': '68e876ee5e055532a492a68b50dd5dd41dd474b6',
                                     'times_seen_consecutively': 7})
        self.evaluator.set_scenario_type(ScenarioType.FILE_COMMIT_GRAM_CHUNK)

        output = b'2'
        self.evaluator.container.exec_run = MagicMock(return_value=(0, output))
        self.evaluator._can_be_cast_to_int = MagicMock(side_effect=lambda x: True)
        result = self.evaluator._evaluate_iteratively_chunk_staged_diff_into_commits()
        self.assertEqual(result, True)


if __name__ == '__main__':
    unittest.main()
