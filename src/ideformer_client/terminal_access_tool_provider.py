import logging
import os
import time
from typing import Optional, Dict
from weakref import finalize

import docker  # type: ignore[import-untyped]
from docker.errors import APIError, ImageNotFound  # type: ignore[import-untyped]
from docker.models.containers import Container  # type: ignore[import-untyped]

from ideformer.client.tools.langchain.implementation import (
    ToolImplementationProvider,
    tool_implementation,
)
from pydantic import Field

from src.ideformer_client.exceptions import ScenarioPreconditionSetupException
from src.ideformer_client.scenario_type import ScenarioType
from src.yt_scripts.get_datapoint_from_dataset import unpack_scenario_for
from src.yt_scripts.schemas import RepositoryDataRow


class TerminalAccessToolImplementationProvider(ToolImplementationProvider):
    # Setup the initial environment for the agent inside the docker container
    # TODO: At this point we already know the first scenario, so it does make sense to include a revision to check out too
    #   However I kinda just want to pull SOME repo, so I will leave this out for now.
    #   For testing I will just hardcode some repo and scenario so that I can develop this further without needing YSON
    DEFAULT_ERROR: str = "ERROR: Could not execute given command."

    def __init__(
            self,
            repository: RepositoryDataRow,
            scenario_type: ScenarioType,
            image: str,
            error_message: Optional[str],
            env_vars: Dict[str, str],
            container_start_timeout: int,
            bash_timeout: Optional[int],
            max_num_chars_bash_output: Optional[int],
            tools_list_endpoint="__tools_list__",
    ):
        super().__init__(tools_list_endpoint=tools_list_endpoint)

        logging.basicConfig(level=logging.INFO)
        self.repository_name = repository.name
        self.repository = repository
        self.image = image
        self.env_vars = env_vars
        self.error_message = error_message or self.DEFAULT_ERROR
        self.container_start_timeout = container_start_timeout
        self.bash_timeout = bash_timeout
        self.max_num_chars_bash_output = max_num_chars_bash_output
        self.scenario_type = scenario_type

        # Unpack and setup scenario
        # TODO: Pretty sure I dont want the tool provider to handle this. Especially the indices of the scenario etc
        self.scenario = unpack_scenario_for(scenario_type=self.scenario_type, repository=repository, scenario_index=0)

        self.client = docker.from_env()
        self.pull_image()
        self.container = self.start_container()

        self.__clone_repository()

        # TODO: Move this into clone repository or its own function, because we must do this every time we cclone
        # a new repository
        err_code, output = self.container.exec_run("/bin/bash -c pwd")
        if err_code == 0:
            self.workdir = output.decode("utf-8").strip() + '/' + self.repository_name.split("/")[-1]
        else:
            raise ValueError("Can't determine working directory.")

        try:
            if self.setup_scenario_preconditions():
                logging.info(f'Setup for ScenarioType.{self.scenario_type.name} successful.')
        except ScenarioPreconditionSetupException as e:
            logging.error(e, exc_info=True)

        finalize(self, self.__docker_stop_containers)

    def __clone_repository(self):
        # Executes the startup command in a blocking way, ensuring that the repository is available before continuing
        startup_command = '/bin/bash -c "git clone https://github.com/{repository}.git"'
        err_code, output = self.container.exec_run(startup_command.format(repository=self.repository_name))

        output = output.decode("utf-8")
        if err_code != 0:
            output = f"{self.error_message}\n{output}"
        logging.info(output)

    def __docker_stop_containers(self):
        if self.container.status == "running":
            self.container.stop()
        self.container.remove()

    def pull_image(self):
        try:
            self.client.images.get(self.image)
            logging.info(f'Found {self.image} locally and using that version of it.')
        except (ImageNotFound, APIError):
            logging.info(f'Found {self.image} not found locally. Attempting to pull from docker hub.')
            repository, tag = self.image, None
            if ":" in repository:
                repository, tag = repository.split(":")
            self.client.images.pull(repository=repository, tag=tag)

    def start_container(self) -> Container:
        # Creates a container with the specified image and environment variables. Runs entrypoint on startup.
        # This specified script is a way with minimal overhead to keep the container alive, which allows us
        # to continuously execute terminal commands provided by the agent.
        container = self.client.containers.create(
            image=self.image, environment=self.env_vars, detach=True, entrypoint="tail -f /dev/null"
        )
        if container.status == "created":
            # Now the command specified in entrypoint is executed
            container.start()

        start_time = time.time()
        while time.time() - start_time < self.container_start_timeout:
            container.reload()
            if container.status == "running":
                logging.info(f"Container for {self.repository_name} started successfully")
                return container
            elif container.status == "exited":
                logging.error(f"Container for {self.repository_name} exited on start.")
                logging.error(f"Container logs: {container.logs()}")
                raise RuntimeError("Could not start container.")
            time.sleep(0.1)

        logging.error(f"Container for {self.repository_name} failed to start within the timeout period")
        raise RuntimeError("Could not start container.")

    def setup_scenario_preconditions(self):
        if self.scenario_type is ScenarioType.FILE_COMMIT_GRAM_CHUNK:
            return self.setup_iteratively_chunk_staged_diff_into_commits()
        elif self.scenario_type is ScenarioType.FILE_COMMIT_GRAM_REBASE:
            return self.setup_clean_local_branch_before_push()
        else:
            raise NotImplementedError(f'Currently only supporting ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_CHUNK.name}'
                                      f'and ScenarioType.{ScenarioType.FILE_COMMIT_GRAM_REBASE.name}.')


    def setup_iteratively_chunk_staged_diff_into_commits(self):
        command = '/bin/bash -c "{command_to_execute}"'

        checkout_command = f"git checkout {self.scenario['first_commit']}"
        err_code, output = self.container.exec_run(command.format(command_to_execute=checkout_command), privileged=False, workdir=self.workdir)
        if err_code == 0:
            # Reset only the changes made to the file concerning the scenario such that they are staged
            reset_command = f"git checkout {self.scenario['last_commit']} -- {self.scenario['file']}"
            err_code, output = self.container.exec_run(command.format(command_to_execute=reset_command), privileged=False, workdir=self.workdir)
            if err_code == 0:
                # TODO this could be removed after debugging or passed to the agent in the initial prompt to remove
                #   a turn that it will use for exploration
                err_code, output = self.container.exec_run(
                    '/bin/bash -c "{command_to_execute}"'.format(command_to_execute='git status'), privileged=False,
                    workdir=self.workdir)
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


    def setup_clean_local_branch_before_push(self):
        """
        This should reduce the amount of commits in the local branch. The intuition is that people might just
        commit some stuff while they are working on it, but the commits might not be maximally cohesive and coherent.

        TODO The length of my chain is incorrect. Let's try and see if the agent can deal with it anyways.
        Returns:

        """
        command = '/bin/bash -c "{command_to_execute}"'

        checkout_command = f"git checkout {self.scenario['first_commit']}"
        err_code, output = self.container.exec_run(command.format(command_to_execute=checkout_command),
                                                   privileged=False, workdir=self.workdir)
        if err_code == 0:
            return True
        else:
            raise ScenarioPreconditionSetupException(f"Cannot check out commit: {self.scenario['first_commit']}. "
                                                     f"Docker error code: {err_code}.")



    @tool_implementation()
    def execute_bash_command(
            self,
            command: str = Field(
                description="A bash command with its arguments to be executed. It can modify the environment and files."
            ),
            reason: str = Field(
                description="A reason why you are calling the tool. For example, 'to change required gradle version' or 'to specify the java sdk'."
            ),
    ):
        """
        Executes a given bash command inside a Docker container.
        """
        # At this point the passed command is just what the agent wants to execute in the terminal. Thus, we still need
        # to prepend the bash call and '-c' flag to execute the command in the string. Note that the command should
        # use double quotes " to ensure it is properly nested in the wrapping string.
        command = f'/bin/bash -c "{command}"'
        logging.info(f'Command to execute in container: {command}')

        if self.bash_timeout is not None:
            command = f"timeout {self.bash_timeout} {command}"
        try:
            if 'sudo' in command or '-rf' in command:
                raise PermissionError(f'Prohibited string "sudo" or "-rf" found in {command}.')

            err_code, output = self.container.exec_run(command, workdir=self.workdir, privileged=False,)
            output = output.decode("utf-8")
            if err_code != 0:
                output = f"{self.error_message}\n{output}"
        except ValueError:
            return self.error_message
        except PermissionError as e:
            return str(e)

        if self.max_num_chars_bash_output is not None:
            return output[: self.max_num_chars_bash_output]

        return output
