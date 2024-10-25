from typing import Optional

from docker.models.containers import Container

import logging

from src.ideformer_client.exceptions import ScenarioEnvironmentException
from src.ideformer_client.scenario_type import ScenarioType
from src.yt_scripts.schemas import RepositoryDataRow

class ScenarioEnvironmentManager:
    # TODO: Right now I'm returning True if a docker command succeeds and otherwise I raise an exception,
    #   However, I'm kinda of just throwing away the return value. That seems not right. Iterate and improve there.

    AGENT_TARGET_BRANCH = 'current-scenario-branch'

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

        Raises:
            NotImplementedError: If the scenario type is not supported.
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
        # TODO: I think I might also need to remove whichever branches the agent created or make sure that it didnt
        #   Touch parts outside of its branch. Not sure how exactly this would be possible?
        err_code, output = self.container.exec_run(
            '/bin/bash -c "{command_to_execute}"'.format(command_to_execute='git reset &&  ' # Reset staged changes
                                                                            'git checkout -- . && ' # Reset workdir
                                                                            f'git checkout {self.default_branch_name}'),
            privileged=False, workdir=self.repository_work_dir)
        if err_code == 0:
            logging.info(f'Successfully tore down the scenario. "git status":\n{self._run_git_status()}')
            return True
        else:
            raise ScenarioEnvironmentException(f"Could not reset repository. Docker error code: {err_code}.")

    def setup_repository(self):
        """
        Clones the repository and sets up the default branch name.

        This method performs the initial setup of the repository by cloning it
        to the local machine. It also retrieves and sets the default branch name
        for the repository.
        """
        self._clone_repository()
        self.default_branch_name = self._get_default_branch_name()

    def teardown_repository(self):
        err_code, output = self.container.exec_run(
            '/bin/bash -c "{command_to_execute}"'.format(command_to_execute=f'rm -r {self.repository_work_dir} && ls'),
            privileged=False)
        if err_code == 0:
            logging.info(f'Successfully removed repository: {self.repository_name} from container. "ls" yields: {output.decode("utf-8")}')
            return True
        else:
            raise ScenarioEnvironmentException(f"Could not reset repository. Docker error code: {err_code}.")

    def provide_scenario_context(self):
        """
        Provides context on the current state of the environment

        Currently includes:
            - git status

        Returns:
            str: A formatted string containing a summary of the current state of the environment
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
        startup_command = '/bin/bash -c "git clone https://github.com/{repository_name}.git"'
        err_code, output = self.container.exec_run(startup_command.format(repository_name=self.repository_name))

        output = output.decode("utf-8")
        if err_code != 0:
            raise ScenarioEnvironmentException(f'Could not clone repository.\n{output}')
        logging.info(output)

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

        Returns:
            bool: True if the branch setup and checkout are successful.

        Raises:
            ScenarioEnvironmentException: If the branch setup and checkout fail, an exception is
                                          raised with the Docker error code.

        """
        err_code, output = self.container.exec_run(
            '/bin/bash -c "{command_to_execute}"'.format(command_to_execute=f'git checkout -b "{self.AGENT_TARGET_BRANCH}"'),
            privileged=False, workdir=self.repository_work_dir)
        if err_code == 0:
            return True
        else:
            raise ScenarioEnvironmentException(f"Could not set up and check out agent branch: {self.AGENT_TARGET_BRANCH}. "
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
