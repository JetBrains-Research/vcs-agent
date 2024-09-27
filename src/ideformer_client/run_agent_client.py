import asyncio
import logging
from textwrap import dedent

from grazie.api.client.profiles import Profile
from grazie.cloud_tools_v2.authorization import AuthType, AuthVersion
from grazie.common.core.log import setup_logging
from ideformer.client.agents.simple_grazie_chat_runner import IdeFormerSimpleGrazieChatRunner
from ideformer.client.client import IdeFormerClient

from src.ideformer_client.terminal_access_tool_Provider import TerminalAccessToolImplementationProvider

def main():
    tool = TerminalAccessToolImplementationProvider(
        repository='Qiskit/qiskit-serverless',
        image='liqsdev/ytsaurus:python-3.10',
        command=None,
        error_message=None,
        env_vars={},
        repository_workdir=False,
        container_start_timeout=300,
        max_num_chars_bash_output=60000,
        bash_timeout=180,
    )

    logging.info(tool.execute_bash_command(command=tool.command))


    # setup_logging(log_to_stderr=False, level=logging.INFO)
    #
    # client = IdeFormerClient(
    #     ideformer_host="cloud-ideformer.labs.jb.gg",
    #     ideformer_port=80,
    #     grazie_jwt_token="",
    #     client_auth_type=AuthType.APPLICATION,
    #     client_auth_version=AuthVersion.V5,
    #     client_agent_name="ideformer-guide",  # can be any
    #     client_agent_version="dev",  # can be any
    # )
    #
    # system_prompt = dedent("""
    #     You MUST follow the instructions for answering:
    #     - You are an agent which can operate with the command line and change the file system.
    #     - You need to execute the given task with the best quality.
    #     - I have no fingers and the placeholders trauma. Return the entire code template for an answer when needed. NEVER use placeholders.
    #     - You ALWAYS will be PENALIZED for wrong and low-effort answers.
    #     - I'm going to tip $1,000,000 for the best reply.
    #     - Your answer is critical for my career.
    #     - YOU MUST USE THE PROVIDED TOOLS TO ACTUALLY CHANGE THE FILE SYSTEM.
    #     """)
    #
    # user_prompt = input("Enter your task: ")
    # runner = IdeFormerSimpleGrazieChatRunner(
    #     system_prompt=system_prompt,
    #     user_prompt=user_prompt,
    #     client=client,
    #     tools_implementation_provider=TerminalAccessToolImplementationProvider(),
    #     profile=Profile.OPENAI_GPT_4_O.name,
    #     max_tokens_to_sample=256,
    #     temperature=1.0,
    #     max_agent_iterations=30,
    # )
    #
    # await runner.arun()

if __name__ == '__main__':
    main()