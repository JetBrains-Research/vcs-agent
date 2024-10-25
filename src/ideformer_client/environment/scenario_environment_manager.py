from typing import Optional

from docker.models.containers import Container

import logging

from src.ideformer_client.exceptions import ScenarioEnvironmentException
from src.ideformer_client.scenario_type import ScenarioType
from src.yt_scripts.schemas import RepositoryDataRow

class ScenarioEnvironmentManager:

    def __init__(self,
                 container: Container,
                 repository: RepositoryDataRow,
                 scenario_type: Optional[ScenarioType] = None,
                 scenario: Optional[dict] = None):
        self.container = container
        self.repository = repository
        self.repository_name = repository.name
        self.scenario_type = scenario_type
        self.scenario = scenario
        self.repository_work_dir = self._get_repository_working_directory()
        self._default_branch_name = None

    def set_scenario(self, scenario: dict):
        self.scenario = scenario

    def set_scenario_type(self, scenario_type: ScenarioType):
        self.scenario_type = scenario_type

    @property
    def default_branch_name(self):
        """
        Returns the default branch name of the repository.

        This method retrieves the default branch name from an internal cache, and if it is not already cached,
        it fetches the name using the `_get_default_branch_name` method.

        Raises:
            ScenarioEnvironmentException: If something went wrong during the initialization.

        Returns:
            str: The name of the default branch.
        """
        if self._default_branch_name is None:
            self._default_branch_name = self._get_default_branch_name()
        return self._default_branch_name

    def setup_scenario_preconditions(self):
        """
        Sets up the preconditions for different scenario types.

        Depending on the scenario type, this method will either:
          - Setup iteratively chunk staged diff into commits.
          - Setup a clean local branch before push.

        Raises:
            NotImplementedError: If the scenario type is not supported.
        """
        if self.scenario is None:
            raise ScenarioEnvironmentException('Cannot setup scenario, since scenario is None.')

        if self.scenario_type is None:
            raise ScenarioEnvironmentException('Cannot setup scenario, since scenario_type is None.')

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
        """
        Clones the git repository of the current repository into the container.

        The repository URL is formed using the `self.repository_name` attribute.
        If the clone operation fails (non-zero error code), an error message
        is logged. Otherwise, the output of the clone operation is logged
        as an info message.

        Raises:
            ScenarioEnvironmentException if the clone operation fails.
        """
        # Executes the startup command in a blocking way, ensuring that the repository is available before continuing
        startup_command = '/bin/bash -c "git clone https://github.com/{repository_name}.git"'
        err_code, output = self.container.exec_run(startup_command.format(repository_name=self.repository_name))

        output = output.decode("utf-8")
        if err_code != 0:
            raise ScenarioEnvironmentException(f'Could not clone repository.\n{output}')
        logging.info(output)

    def teardown_repository(self):
        raise NotImplementedError

    def provide_scenario_context(self):
        """
        Provides context on the current state of the environment

        Currently includes:
            - git status

        Returns:
            str: A formatted string containing a summary of the current state of the environment
        """
        return self._run_git_status()

    def _get_default_branch_name(self):
        """
        Retrieves the default branch name from the output of the "git status" command. Run right after cloning the
        repository.

        Returns:
            str: The name of the default branch.

        Raises:
            ScenarioEnvironmentException: If the output of "git status" does not contain the branch information or if the output is empty.
        """
        output = self._run_git_status()

        lines = output.splitlines()
        if len(lines) > 0:
            first_line = lines[0]
            if 'On branch' in first_line:
                return first_line.split('On branch ')[1].strip()
            else:
                raise ScenarioEnvironmentException(f'"git status" did not contain default branch: {output}')
        else:
            raise ScenarioEnvironmentException(f'Cannot parse "git status" output, nothing to parse: {output}')

    def _run_git_status(self):
        err_code, output = self.container.exec_run(
            '/bin/bash -c "{command_to_execute}"'.format(command_to_execute='git status'),
            privileged=False, workdir=self.repository_work_dir)
        if err_code == 0:
            return output.decode("utf-8")
        else:
            raise ScenarioEnvironmentException(f"Cannot get git status. Docker error code: {err_code}.")

    def _get_repository_working_directory(self):
        """
        Gets the repository working directory inside the container.

        This method runs a shell command to get the present working directory inside the container.
        It appends the repository name (sans any preceding path) to this directory and sets the repository
        working directory for the instance and returns the result. Does not require the repository to be cloned already.

        Raises:
            ValueError: If the working directory can't be determined.

        Returns:
            str: Absolute path to the repository working directory for the repository.
        """
        err_code, output = self.container.exec_run("/bin/bash -c pwd")
        if err_code == 0:
            return output.decode("utf-8").strip() + '/' + self.repository_name.split("/")[-1]
        else:
            raise ValueError("Can't determine working directory.")

    def _setup_iteratively_chunk_staged_diff_into_commits(self) -> bool:
        """
        Sets up the environment of the Docker container for iteratively chunking the staged difference in the repository into multiple commits.

        Checks out the first (ie. chronologically newest) commit in the scenario and then soft resets the changes of the file
        specified in the scenario to stage the differences between the first (ie. newest) and last (ie. oldest) commit.


        Raises:
            ScenarioEnvironmentException: If an error occurs during checkout or reset commands within the Docker container.

        Returns:
            bool: whether the setup was successful
        """
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
                logging.info('Scenario precondition successfully set up.')
                return True
            else:
                raise ScenarioEnvironmentException(f"Cannot check out commit: {self.scenario['last_commit']} and "
                                                         f"soft reset changes in {self.scenario['file']}. Docker error "
                                                         f"code: {err_code}.")
        else:
            raise ScenarioEnvironmentException(f"Cannot check out commit: {self.scenario['first_commit']}. Docker "
                                                     f"error code: {err_code}.")


    def _setup_clean_local_branch_before_push(self):
        """
        Sets up the environment of the Docker container for cleaning the local tree (ie. rebase) in the repository before pushing.

        Checks out the first (ie. chronologically newest) commit in the scenario.

        Raises:
            ScenarioEnvironmentException: If the checkout command fails.

        Returns:
            bool: whether the setup was successful
        """
        command = '/bin/bash -c "{command_to_execute}"'

        checkout_command = f"git checkout {self.scenario['first_commit']}"
        err_code, output = self.container.exec_run(command.format(command_to_execute=checkout_command),
                                                   privileged=False, workdir=self.repository_work_dir)
        if err_code == 0:
            return True
        else:
            raise ScenarioEnvironmentException(f"Cannot check out commit: {self.scenario['first_commit']}. "
                                                     f"Docker error code: {err_code}.")
