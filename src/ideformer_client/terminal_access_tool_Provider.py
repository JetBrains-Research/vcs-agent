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


class TerminalAccessToolImplementationProvider(ToolImplementationProvider):
    # Setup the initial environment for the agent inside the docker container
    # TODO: At this point we already know the first scenario, so it does make sense to include a revision to check out too
    #   However I kinda just want to pull SOME repo, so I will leave this out for now.
    #   For testing I will just hardcode some repo and scenario so that I can develop this further without needing YSON
    # The image we are using is built on Python 3.10 and includes git, so no need to install it here.
    DEFAULT_COMMAND: str = (# Ensure that the container does not exit immediately after finishing the setup.
                            # Give some time to specify the agents task and start it up.
                            "while true; do sleep 1000; done")
    DEFAULT_ERROR: str = "ERROR: Could not execute given command."

    def __init__(
            self,
            repository: str,
            image: str,
            command: Optional[str],
            error_message: Optional[str],
            env_vars: Dict[str, str],
            repository_workdir: bool,
            container_start_timeout: int,
            bash_timeout: Optional[int],
            max_num_chars_bash_output: Optional[int],
            tools_list_endpoint="__tools_list__",
    ):
        super().__init__(tools_list_endpoint=tools_list_endpoint)

        logging.basicConfig(level=logging.INFO)

        self.repository = repository
        self.image = image
        self.env_vars = env_vars
        self.repository_workdir = repository_workdir

        # The initial command is executed in self.start_container(). In the creation command the entrypoint specifies
        # to which command line tool the command is passed. Thus the command should be a well-defined bash command,
        # if we want to run it in bash. Here we prepend '-c' to ensure this.
        self.command = (
            f"-c \"{self.DEFAULT_COMMAND.format(repository=repository, repository_dir=repository.split('/')[-1])}\""
            if command is None
            else f"-c \"{command.format(repository=repository, repository_dir=repository.split('/')[-1])}\""
        )
        self.error_message = error_message or self.DEFAULT_ERROR
        self.container_start_timeout = container_start_timeout
        self.bash_timeout = bash_timeout
        self.max_num_chars_bash_output = max_num_chars_bash_output

        self.client = docker.from_env()
        self.pull_image()
        self.container = self.start_container()

        # Only the initial start-up command is run in bash through the entrypoint specified, thus we need to also
        # prepend it again here. Same as in the actual tool call.
        err_code, output = self.container.exec_run("/bin/bash -c pwd")
        if err_code == 0:
            self.workdir = output.decode("utf-8").strip()
        else:
            raise ValueError("Can't determine working directory.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__docker_stop_containers()

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
        # Creates a container with the specified image and environment variables. Also primes the container to run
        # self.command on start-up with the command line tool specified in 'entrypoint'.
        container = self.client.containers.create(
            image=self.image, command=self.command, environment=self.env_vars, detach=True, entrypoint="/bin/bash"
        )
        if container.status == "created":
            # Now the command is executed
            container.start()

        start_time = time.time()
        while time.time() - start_time < self.container_start_timeout:
            container.reload()
            if container.status == "running":
                # Note that it is not guaranteed that the start-up command has already concluded at this point.
                logging.info(f"Container for {self.repository} started successfully")
                return container
            elif container.status == "exited":
                logging.error(f"Container for {self.repository} exited on start.")
                logging.error(f"Container logs: {container.logs()}")
                raise RuntimeError("Could not start container.")
            time.sleep(0.1)

        logging.error(f"Container for {self.repository} failed to start within the timeout period")
        raise RuntimeError("Could not start container.")

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
            if self.repository_workdir:
                err_code, output = self.container.exec_run(
                    command, workdir=self.workdir + '/' + self.repository.split("/")[-1], privileged=False,
                )
            else:
                err_code, output = self.container.exec_run(command)
            output = output.decode("utf-8")
            if err_code != 0:
                output = f"{self.error_message}\n{output}"
        except ValueError:
            return self.error_message

        if self.max_num_chars_bash_output is not None:
            return output[: self.max_num_chars_bash_output]

        return output
