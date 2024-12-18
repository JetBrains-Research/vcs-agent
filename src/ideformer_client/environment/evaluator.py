from typing import Optional

from docker.models.containers import Container

from src.ideformer_client.environment.scenario_type import ScenarioType
from src.ideformer_client.utils.exceptions import ScenarioEnvironmentException


class Evaluator:

    def __init__(self,
                 container: Container,
                 agent_target_branch_name: str,
                 repository_work_dir: str,
                 scenario_type: Optional[ScenarioType] = None,
                 scenario: Optional[dict] = None):
        self.container = container
        self.agent_target_branch_name = agent_target_branch_name
        self.repository_work_dir = repository_work_dir
        self.scenario_type = scenario_type
        self.scenario = scenario
        self.command_template = '/bin/bash -c "{command_to_execute}"'

    def set_scenario(self, scenario: dict):
        self.scenario = scenario

    def set_scenario_type(self, scenario_type: ScenarioType):
        self.scenario_type = scenario_type

    def evaluate(self) -> bool:
        """
            Evaluates the configured scenario.

            Raises:
                NotImplementedError: If the scenario type is not supported.
                ScenarioEnvironmentException: If scenario or scenario_type are not initialized or the evaluation failed.

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
        elif self.scenario_type is ScenarioType.MERGE:
            return self._evaluate_diff_between_head_and(self.scenario['merge_commit_hash'])
        elif self.scenario_type is ScenarioType.CHERRY_PICK:
            return self._evaluate_diff_between_head_and(self.scenario['cherry_pick_commit'])
        else:
            raise NotImplementedError(
                f'Currently only supporting ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_CHUNK.name}'
                f'and ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_REBASE.name}.')

    def _evaluate_iteratively_chunk_staged_diff_into_commits(self):
        """
        Checks whether the agent successfully split the large staged diff into multiple commits and whether
        all the original changes are still present.

        Evaluates to True if:
            - Agent made > 1 commit
            - The state of the agent's branch HEAD is the same (diff is empty) as the chronologically newest commit
                in the scenario (scenario['first_commit']), ie agent did not introduce changes in the code.

        Raises:
            ScenarioEnvironmentException: If there is an error executing the command inside the container.

        Returns:
            bool: True if the agent correctly split the staged changes into >1 commits and if the commits contain all
                of the original data, otherwise False.
        """
        err_code, output = self.container.exec_run(
            self.command_template.format(command_to_execute=self._get_git_file_commit_gram_evaluation_command()),
            privileged=False, workdir=self.repository_work_dir)

        if err_code != 0:
            raise ScenarioEnvironmentException(f"Cannot evaluate scenario: {output.decode('utf-8')}")

        amount_of_commits_made_by_agent = output.decode("utf-8").strip()

        return self._can_be_cast_to_int(amount_of_commits_made_by_agent) and int(amount_of_commits_made_by_agent) > 1

    def _evaluate_clean_local_branch_before_push(self):
        """
        Checks whether the agent successfully cleaned the local branch and whether all the original changes are still present.

        Evaluates to True if:
            - Agent branch has < scenario['times_seen_consecutively'] commits
            - The state of the agent's branch HEAD is the same (diff is empty) as the chronologically newest commit
                in the scenario (scenario['first_commit'])

        Raises:
            ScenarioEnvironmentException: If there is an error executing the command inside the container.

        Returns:
            bool: True if the agent correctly condensed changes into < scenario['times_seen_consecutively'] commits
                and if the commits contain all of the original data, otherwise False.
        """
        err_code, output = self.container.exec_run(
            self.command_template.format(command_to_execute=self._get_git_file_commit_gram_evaluation_command()),
            privileged=False, workdir=self.repository_work_dir)

        if err_code != 0:
            raise ScenarioEnvironmentException(f"Cannot evaluate scenario: {output.decode('utf-8')}")

        cleaned_output = output.decode("utf-8").strip()

        return (self._can_be_cast_to_int(cleaned_output) and 0 < int(cleaned_output) <= self.scenario[
            'times_seen_consecutively'])

    def _evaluate_diff_between_head_and(self, ground_truth_commit: str):
        """
        Checks whether the agent successfully performed the merge and did not introduce any unwanted changes
        when resolving a merge conflict.

        Evaluates to True if the state of the agent's branch HEAD is the same (diff is empty) as the ground truth merge commit.
        This implicitly also evaluates whether a merge was carried out at all, because if that is not the case, there
        would be a diff.

        Raises:
            ScenarioEnvironmentException: If there is an error executing the command inside the container.

        Returns:
            bool: True if the agent carried out the merge and did not introduce unwanted changes with respect
                to the ground truth merge commit, otherwise False.
        """
        err_code, output = self.container.exec_run(
            self.command_template.format(command_to_execute=self._get_git_diff_evaluation_command(ground_truth_commit)),
            privileged=False, workdir=self.repository_work_dir)

        if err_code != 0:
            raise ScenarioEnvironmentException(f"Cannot evaluate scenario: {output.decode('utf-8')}")

        diff = output.decode("utf-8").strip()

        return diff == ''

    def _get_git_diff_evaluation_command(self, ground_truth_commit: str):
        """
        Returns the differences between the scenario's ground truth merge commit and the agent's target branch HEAD.

        Returns:
            str: The constructed shell command to execute the described git operations.
        """
        return f"git diff {ground_truth_commit} {self.agent_target_branch_name}"

    def _get_git_file_commit_gram_evaluation_command(self):
        """
        Generates a command to evaluate git file commit and gram scenarios.

        Constructs a shell command to perform two git operations:
        1. Display differences between the scenario's first commit and the agent's target branch HEAD for a given file.
        2. Count the number of commits between the scenario's last commit and the agent's target branch HEAD. The output is
            0-based, so it only counts commits ontop of self.scenario['last_commit'], excluding that commit.

        Returns:
            str: The constructed shell command to execute the described git operations.
        """
        return f"git diff {self.scenario['first_commit']} {self.agent_target_branch_name}" \
                    f" -- {self.scenario['file']} && git rev-list --count {self.scenario['last_commit']}..{self.agent_target_branch_name}"

    def _can_be_cast_to_int(self, str):
        """
        Checks if a given string can be converted to an integer.

        Args:
            str: The input string to check if it can be converted to an integer.

        Returns:
            bool: True if the string can be converted to an integer, False otherwise.
        """
        try:
            int(str)
            return True
        except ValueError:
            return False