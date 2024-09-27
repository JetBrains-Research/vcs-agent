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
    #     grazie_jwt_token="eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJHcmF6aWUgQXV0aGVudGljYXRpb24iLCJ1aWQiOiI1YzQ1ZDU5Ni1kMWEzLTRlYjMtYmFhNy01NjE4N2ZkZWU5M2UiLCJ0eXBlIjoiY3VzdG9tIiwibGljZW5zZSI6ImN1c3RvbV9hcHA6NjE4NWZjNDItZWYxNi00OTk3LWE2NzEtZjk3Y2E2NjhkMTNmIiwibGljZW5zZV90eXBlIjoiamV0YnJhaW5zLWFpLmFwcGxpY2F0aW9uLnN0YW5kYXJkIiwiZXhwIjoxNzQ5MTkyNTQwfQ.AQgycIu9J2JFzZDBtkWK7sb0YMwrGWn4CLQDrw7T2ft6tUU2VdSrj_9pegddXZ-A1DPUr_be2YVj_yOV3KNqIjN_wNTS8KFpQ44HQNEHLjAr_6c6eTFZ0aJRMBxXXz4g9-Uz3W8ZkGcnIBeLAC4xggPEpOgRtfmxMOaFJdF5AVe3eHCVGdSii4bomv3P_NL22BZZXQvCuZj7d7ZGwe7NQN5CBqsrM5D15vTrXzaQ1KFE9sJfUfWo76I05msr2wUUGv0Lo34JZYPXxXTIKgB4gPfdefgNn4jcxPTCvY5-Vlqb_NZTbr_-mETlhF7jNeKhpJvDREfNVsgnrJlm9Vv8EQ",
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