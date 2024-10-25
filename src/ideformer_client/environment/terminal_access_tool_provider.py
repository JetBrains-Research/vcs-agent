import logging
from typing import Optional

from docker.models.containers import Container

from ideformer.client.tools.langchain.implementation import (
    ToolImplementationProvider,
    tool_implementation,
)
from pydantic import Field


class TerminalAccessToolImplementationProvider(ToolImplementationProvider):
    DEFAULT_ERROR: str = "ERROR: Could not execute given command."

    def __init__(
            self,
            container: Container,
            error_message: Optional[str],
            bash_timeout: Optional[int],
            max_num_chars_bash_output: Optional[int],
            workdir: str,
            tools_list_endpoint="__tools_list__",
    ):
        super().__init__(tools_list_endpoint=tools_list_endpoint)

        self.error_message = error_message or self.DEFAULT_ERROR
        self.bash_timeout = bash_timeout
        self.max_num_chars_bash_output = max_num_chars_bash_output
        self.container = container
        self.workdir = workdir

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

            err_code, output = self.container.exec_run(command, workdir=self.workdir, privileged=False)
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
