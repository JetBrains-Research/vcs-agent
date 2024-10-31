from typing import Optional

from docker.models.containers import Container

from src.ideformer_client.environment.scenario_type import ScenarioType
from src.ideformer_client.utils.exceptions import ScenarioEnvironmentException


class Evaluator:

    def __init__(self,
                 container: Container,
                 agent_target_branch_name: str,
                 scenario_type: Optional[ScenarioType] = None,
                 scenario: Optional[dict] = None):
        self.container = container
        self.agent_target_branch_name = agent_target_branch_name
        self.scenario_type = scenario_type
        self.scenario = scenario

    def set_scenario(self, scenario: dict):
        self.scenario = scenario

    def set_scenario_type(self, scenario_type: ScenarioType):
        self.scenario_type = scenario_type

    def evaluate(self) -> bool:
        """
            Evaluates the configured scenario.

            Raises:
                NotImplementedError: If the scenario type is not supported.
                ScenarioEnvironmentException: If scenario or scenario_type are not initialized.

            Returns:
                bool: True if the scenario was successfully and correctly solved, False otherwise.
        """
        if self.scenario is None:
            raise ScenarioEnvironmentException('Cannot evaluate scenario, since scenario is None.')

        if self.scenario_type is None:
            raise ScenarioEnvironmentException('Cannot evaluate scenario, since scenario_type is None.')

        if self.scenario_type is ScenarioType.FILE_COMMIT_GRAM_CHUNK:
            return self._evaluate_iteratively_chunk_staged_diff_into_commits()
        elif self.scenario_type is ScenarioType.FILE_COMMIT_GRAM_REBASE:
            return self._evaluate_clean_local_branch_before_push()
        else:
            raise NotImplementedError(
                f'Currently only supporting ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_CHUNK.name}'
                f'and ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_REBASE.name}.')

    def _evaluate_iteratively_chunk_staged_diff_into_commits(self):
        return False

    def _evaluate_clean_local_branch_before_push(self):
        return False