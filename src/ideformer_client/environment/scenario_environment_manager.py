from docker.models.containers import Container

import logging

from src.ideformer_client.exceptions import ScenarioPreconditionSetupException
from src.ideformer_client.scenario_type import ScenarioType
from src.yt_scripts.schemas import RepositoryDataRow

class ScenarioEnvironmentManager:
    def __init__(self,
                 container: Container,
                 repository: RepositoryDataRow,
                 scenario_type: ScenarioType,
                 scenario: dict):
        self.container = container
        self.repository = repository
        self.repository_name = repository.name
        self.scenario_type = scenario_type
        self.scenario = scenario
        self.repository_work_dir = None

        self._setup_repository_working_directory()

    def setup_scenario_preconditions(self):
        if self.scenario_type is ScenarioType.FILE_COMMIT_GRAM_CHUNK:
            return self._setup_iteratively_chunk_staged_diff_into_commits()
        elif self.scenario_type is ScenarioType.FILE_COMMIT_GRAM_REBASE:
            return self._setup_clean_local_branch_before_push()
        else:
            raise NotImplementedError(
                f'Currently only supporting ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_CHUNK.name}'
                f'and ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_REBASE.name}.')

    def teardown_scenario(self):
        raise NotImplementedError

    def clone_repository(self):
        # Executes the startup command in a blocking way, ensuring that the repository is available before continuing
        startup_command = '/bin/bash -c "git clone https://github.com/{repository_name}.git"'
        err_code, output = self.container.exec_run(startup_command.format(repository_name=self.repository_name))

        output = output.decode("utf-8")
        if err_code != 0:
            logging.error(f"Could not clone repository.\n{output}")
        logging.info(output)

    def teardown_repository(self):
        raise NotImplementedError

    def provide_scenario_context(self):
        raise NotImplementedError

    def _setup_repository_working_directory(self):
        err_code, output = self.container.exec_run("/bin/bash -c pwd")
        if err_code == 0:
            self.repository_work_dir = output.decode("utf-8").strip() + '/' + self.repository_name.split("/")[-1]
        else:
            raise ValueError("Can't determine working directory.")

    def _setup_iteratively_chunk_staged_diff_into_commits(self):
        command = '/bin/bash -c "{command_to_execute}"'

        checkout_command = f"git checkout {self.scenario['first_commit']}"
        err_code, output = self.container.exec_run(command.format(command_to_execute=checkout_command),
                                                   privileged=False, workdir=self.repository_work_dir)
        if err_code == 0:
            # Reset only the changes made to the file concerning the scenario such that they are staged
            reset_command = f"git checkout {self.scenario['last_commit']} -- {self.scenario['file']}"
            err_code, output = self.container.exec_run(command.format(command_to_execute=reset_command),
                                                       privileged=False, workdir=self.repository_work_dir)
            if err_code == 0:
                # TODO this could be removed after debugging or passed to the agent in the initial prompt to remove
                #   a turn that it will use for exploration
                err_code, output = self.container.exec_run(
                    '/bin/bash -c "{command_to_execute}"'.format(command_to_execute='git status'),
                    privileged=False, workdir=self.repository_work_dir)

                if err_code == 0:
                    logging.info(output.decode('utf-8'))
                    return True
                else:
                    raise ScenarioPreconditionSetupException(f"Could not fetch the current status of the git repository."
                                                             f" Docker error code: {err_code}.")
            else:
                raise ScenarioPreconditionSetupException(f"Cannot check out commit: {self.scenario['last_commit']} and "
                                                         f"soft reset changes in {self.scenario['file']}. Docker error "
                                                         f"code: {err_code}.")
        else:
            raise ScenarioPreconditionSetupException(f"Cannot check out commit: {self.scenario['first_commit']}. Docker "
                                                     f"error code: {err_code}.")


    def _setup_clean_local_branch_before_push(self):
        """
        This should reduce the amount of commits in the local branch. The intuition is that people might just
        commit some stuff while they are working on it, but the commits might not be maximally cohesive and coherent.

        TODO The length of my chain is incorrect. Let's try and see if the agent can deal with it anyways.
        Returns:

        """
        command = '/bin/bash -c "{command_to_execute}"'

        checkout_command = f"git checkout {self.scenario['first_commit']}"
        err_code, output = self.container.exec_run(command.format(command_to_execute=checkout_command),
                                                   privileged=False, workdir=self.repository_work_dir)
        if err_code == 0:
            return True
        else:
            raise ScenarioPreconditionSetupException(f"Cannot check out commit: {self.scenario['first_commit']}. "
                                                     f"Docker error code: {err_code}.")
