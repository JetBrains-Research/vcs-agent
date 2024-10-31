from typing import Optional

from docker.models.containers import Container

import logging

from src.ideformer_client.utils.exceptions import ScenarioEnvironmentException
from src.ideformer_client.environment.scenario_type import ScenarioType
from src.yt_scripts.schemas import RepositoryDataRow

class ScenarioEnvironmentManager:
    AGENT_TARGET_BRANCH_NAME = 'current-scenario-branch'

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
        self.default_branch_name = None
        self.command_template = '/bin/bash -c "{command_to_execute}"'

    def set_scenario(self, scenario: dict):
        self.scenario = scenario

    def set_scenario_type(self, scenario_type: ScenarioType):
        self.scenario_type = scenario_type

    def setup_scenario_preconditions(self):
        """
        Sets up the preconditions for different scenario types.

        Depending on the scenario type, this method will either:
          - Set up iteratively chunk staged diff into commits.
          - Set up a clean local branch before push.

        For all scenario types a new branch with the name in self.AGENT_TARGET_BRANCH_NAME is created and checked out to
        isolate the agent actions from the rest of the repository.

        Raises:
            NotImplementedError: If the scenario type is not supported.
            ScenarioEnvironmentException: If scenario or scenario_type are not initialized. Also, if the branch setup failed.
        """
        if self.scenario is None:
            raise ScenarioEnvironmentException('Cannot setup scenario, since scenario is None.')

        if self.scenario_type is None:
            raise ScenarioEnvironmentException('Cannot setup scenario, since scenario_type is None.')

        if self.scenario_type is ScenarioType.FILE_COMMIT_GRAM_CHUNK:
            self._setup_iteratively_chunk_staged_diff_into_commits()
        elif self.scenario_type is ScenarioType.FILE_COMMIT_GRAM_REBASE:
            self._setup_clean_local_branch_before_push()
        else:
            raise NotImplementedError(
                f'Currently only supporting ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_CHUNK.name}'
                f'and ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_REBASE.name}.')

        # In any case, the agent's actions should be isolated into a specific branch that is set up in a deterministic
        # way. This saves a turn and avoids fuzzy naming of the branch and resulting difficulties in the teardown.
        self._setup_agent_branch()

    def teardown_scenario(self):
        """
        Resets the repository to its default state after a scenario has been executed.

        This involves resetting staged changes, resetting the working directory, and removing the agent's target branch.
        Upon successful completion, validates that the target branch has been removed.

        Raises:
            ScenarioEnvironmentException: If the reset operation fails or if the
            target branch is still present after the reset.
        """
        teardown_command_err_code, teardown_output = self.container.exec_run(
            '/bin/bash -c "{command_to_execute}"'\
                .format(command_to_execute='git reset --hard HEAD &&  ' # Reset any changes staged or unstaged and workdir
                                            f'git checkout {self.default_branch_name} &&'
                                            # Remove the branch in which the agent attempted to solve this scenario
                                            # and force removal from the repository entirely, by triggering garbage collection
                                            # Reading Note: `git prune` could end up being to costly to run after every scenario.
                                            #   Monitor this.
                                            f'git branch -D {self.AGENT_TARGET_BRANCH_NAME} && '
                                            'git prune'),
            privileged=False, workdir=self.repository_work_dir)
        validation_command_err_code, validation_output = self.container.exec_run(
            '/bin/bash -c "{command_to_execute}"'.format(command_to_execute=f'git branch --list {self.AGENT_TARGET_BRANCH_NAME}'),
            privileged=False, workdir=self.repository_work_dir)
        if teardown_command_err_code == 0 and validation_command_err_code == 0 and validation_output == b'':
            logging.info(f'Successfully tore down the scenario.')
        else:
            raise ScenarioEnvironmentException(f"Could not reset repository. Command output: {teardown_output.decode('utf-8')}."
                                               f"\nBranch deletion validation (empty string if successful): {validation_output.decode('utf-8')}"
                                               f"\nDocker error code: {teardown_command_err_code}.")

    def setup_repository(self):
        """
        Clones the repository and sets up the default branch name.

        This method performs the initial setup of the repository by cloning it
        to the local machine. It also retrieves and sets the default branch name
        for the repository.

        Raises:
            ScenarioEnvironmentException: If either the cloning or setup of the default branch name fail.
        """
        self._clone_repository()
        self.default_branch_name = self._get_default_branch_name()

    def teardown_repository(self):
        """
        Remove the repository from the container.

        Removes the repository directory with `rm -r` and then lists the remaining files for debugging purposes.

        Raises:
            ScenarioEnvironmentException: If the repository could not be reset, indicated by a non-zero Docker error code.
        """
        err_code, output = self.container.exec_run(
            '/bin/bash -c "{command_to_execute}"'.format(command_to_execute=f'rm -r {self.repository_work_dir} && ls'),
            privileged=False)
        if err_code == 0:
            logging.info(f'Successfully removed repository: {self.repository_name} from container.')
            logging.debug(f'"ls" yields: {output.decode("utf-8")}')
        else:
            raise ScenarioEnvironmentException(f"Could not reset repository. Docker error code: {err_code}.")

    def provide_scenario_context(self):
        """
        Provides context on the current state of the environment

        Currently includes:
            - git status

        Returns:
            str: A formatted string containing a summary of the current state of the environment

        Raises:
            ScenarioEnvironmentException: If the context cannot be fetched (git status fails).
        """
        return self._run_git_status()

    def _clone_repository(self):
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
        clone_command = '/bin/bash -c "git clone https://github.com/{repository_name}.git"'
        err_code, output = self.container.exec_run(clone_command.format(repository_name=self.repository_name))

        output = output.decode("utf-8")
        if err_code != 0:
            raise ScenarioEnvironmentException(f'Could not clone repository {self.repository_name}:\n{output}')
        else:
            logging.info(f'Successfully cloned repository {self.repository_name}:\n{output}')

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

    def _setup_agent_branch(self):
        """
        Sets up the branch isolating the agent's actions from the rest of the repository.

        This method creates and checks out a new branch specified by AGENT_TARGET_BRANCH in the
        repository residing in the Docker container.

        Raises:
            ScenarioEnvironmentException: If the branch setup and checkout fail, an exception is
                                          raised with the Docker error code.

        """
        err_code, output = self.container.exec_run(
            '/bin/bash -c "{command_to_execute}"'.format(command_to_execute=f'git checkout -b "{self.AGENT_TARGET_BRANCH_NAME}"'),
            privileged=False, workdir=self.repository_work_dir)
        if err_code == 0:
            logging.info(f'Successfully set up branch for agent actions: {self.AGENT_TARGET_BRANCH_NAME}.')
            logging.debug(f'"git status" after setup:\n{self._run_git_status()}')
        else:
            raise ScenarioEnvironmentException(f"Could not set up and check out agent branch: {self.AGENT_TARGET_BRANCH_NAME}. "
                                               f"Docker error code: {err_code}.")

    def _run_git_status(self):
        """
        Executes the `git status` command in a Docker container and returns its output.

        This method runs the `git status` command in the specified working directory
        of a Docker container. If the command is executed successfully, its output
        is decoded and returned. Otherwise, a ScenarioEnvironmentException is raised
        with the corresponding Docker error code.

        Returns:
            str: The output of the `git status` command if successful.

        Raises:
            ScenarioEnvironmentException: If the execution of the `git status` command in the Docker container fails.
        """
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

    def _setup_iteratively_chunk_staged_diff_into_commits(self):
        """
        Sets up the environment of the Docker container for iteratively chunking the staged difference in the repository into multiple commits.

        Checks out the first (ie. chronologically newest) commit in the scenario and then soft resets the changes of the file
        specified in the scenario to stage the differences between the first (ie. newest) and last (ie. oldest) commit.


        Raises:
            ScenarioEnvironmentException: If an error occurs during checkout or reset commands within the Docker container.
        """
        checkout_command = f"git checkout {self.scenario['first_commit']}"
        err_code, output = self.container.exec_run(self.command_template.format(command_to_execute=checkout_command),
                                                   privileged=False, workdir=self.repository_work_dir)
        if err_code == 0:
            # Reset only the changes made to the file concerning the scenario such that they are staged
            reset_command = f"git checkout {self.scenario['last_commit']} -- {self.scenario['file']}"
            err_code, output = self.container.exec_run(self.command_template.format(command_to_execute=reset_command),
                                                       privileged=False, workdir=self.repository_work_dir)
            if err_code != 0:
                raise ScenarioEnvironmentException(f"Cannot check out commit: {self.scenario['last_commit']} and "
                                                   f"soft reset changes in {self.scenario['file']}. Docker error "
                                                   f"code: {err_code}.")
            else:
                logging.info(f'Scenario precondition for {self.scenario_type} successfully set up.')

        else:
            raise ScenarioEnvironmentException(f"Cannot check out commit: {self.scenario['first_commit']}. Docker "
                                                     f"error code: {err_code}.")


    def _setup_clean_local_branch_before_push(self):
        """
        Sets up the environment of the Docker container for cleaning the local tree (ie. rebase) in the repository before pushing.

        Checks out the first (ie. chronologically newest) commit in the scenario.

        Raises:
            ScenarioEnvironmentException: If the checkout command fails.
        """
        checkout_command = f"git checkout {self.scenario['first_commit']}"
        err_code, output = self.container.exec_run(self.command_template.format(command_to_execute=checkout_command),
                                                   privileged=False, workdir=self.repository_work_dir)
        if err_code != 0:
            raise ScenarioEnvironmentException(f"Cannot check out commit: {self.scenario['first_commit']}. "
                                                     f"Docker error code: {err_code}.")
        else:
            logging.info(f'Scenario precondition for {self.scenario_type} successfully set up.')
