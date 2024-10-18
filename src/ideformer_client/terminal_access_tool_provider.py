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

        self.__clone_repository_and_change_working_dir_to_it()

        # TODO: Move this into clone repository or its own function, because we must do this every time we cclone
        # a new repository
        err_code, output = self.container.exec_run("/bin/bash -c pwd")
        if err_code == 0:
            self.workdir = output.decode("utf-8").strip() + '/' + self.repository_name.split("/")[-1]
        else:
            raise ValueError("Can't determine working directory.")

        try:
            self.setup_iteratively_chunk_commits_into_cohesive_units()
        except RuntimeError as e:
            logging.error(e, exc_info=True)

        finalize(self, self.__docker_stop_containers)

    def __clone_repository(self):
        # Executes the startup command in a blocking way, ensuring that the repository is available before continuing
        startup_command = '/bin/bash -c "git clone https://github.com/{repository}.git"'
        self.container.exec_run(startup_command.format(repository=self.repository))

    def __docker_stop_containers(self):
        logging.info(self.container.logs())
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
                logging.info(f"Container for {self.repository} started successfully")
                return container
            elif container.status == "exited":
                logging.error(f"Container for {self.repository} exited on start.")
                logging.error(f"Container logs: {container.logs()}")
                raise RuntimeError("Could not start container.")
            time.sleep(0.1)

        logging.error(f"Container for {self.repository} failed to start within the timeout period")
        raise RuntimeError("Could not start container.")

    def setup_iteratively_chunk_commits_into_cohesive_units(self):
        # TODO: This function should be in a parent that delegates to an implementation that is specific to each type of supported scenario.
        # Somehow I need to specify which type of scenario to run. For now I will just implement iterative
        # chunk committing.
        checkout_command = f"git checkout {self.scenario['first_commit']}"
        command = '/bin/bash -c "{command_to_execute}"'.format(command_to_execute=checkout_command)
        err_code, output = self.container.exec_run(command, privileged=False, workdir=self.workdir + '/' + self.repository.split("/")[-1])
        if err_code == 0:
            reset_command = f"git checkout {self.scenario['last_commit']} -- {self.scenario['file']}"
            command = '/bin/bash -c "{command_to_execute}"'.format(command_to_execute=reset_command)
            err_code, output = self.container.exec_run(command, privileged=False, workdir=self.workdir + '/' + self.repository.split("/")[-1])
            if err_code == 0:
                return True
            else:
                raise RuntimeError(f"Cannot check out commit: {self.scenario['last_commit']} and soft reset changes in"
                                   f"{self.scenario['file']}.")
        else:
            raise RuntimeError(f"Cannot check out commit: {self.scenario['first_commit']}.")

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

            if self.repository_workdir:
                err_code, output = self.container.exec_run(
                    command, workdir=self.workdir + '/' + self.repository.split("/")[-1], privileged=False,
                )
            else:
                err_code, output = self.container.exec_run(command, privileged=False)
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
