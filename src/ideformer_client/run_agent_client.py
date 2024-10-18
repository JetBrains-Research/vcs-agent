import asyncio
import logging
import os
from textwrap import dedent

from grazie.api.client.profiles import Profile
from grazie.cloud_tools_v2.authorization import AuthType, AuthVersion
from grazie.common.core.log import setup_logging
from ideformer.client.agents.simple_grazie_chat_runner import IdeFormerSimpleGrazieChatRunner
from ideformer.client.client import IdeFormerClient

from src.ideformer_client.data.git_dataset_provider import GitDatasetProvider
from src.ideformer_client.data.yt_connection_manager import YTConnectionManager
from src.ideformer_client.scenario_type import ScenarioType
from src.ideformer_client.terminal_access_tool_provider import TerminalAccessToolImplementationProvider


async def main():
    setup_logging(log_to_stderr=False, level=logging.INFO)

    yt_connection_manager = YTConnectionManager(dataset_table_location=os.environ['YT_DATASET_TABLE_LOCATION'])
    response = yt_connection_manager.get_dataset_stream()
    git_dataset_provider = GitDatasetProvider(response)

    for repository in git_dataset_provider.stream_repositories():
        scenario_type: ScenarioType = ScenarioType.FILE_COMMIT_GRAM_REBASE

        scenarios = git_dataset_provider.get_scenarios_for(scenario_type=scenario_type)

        tool = TerminalAccessToolImplementationProvider(
            repository=repository,
            scenario_type=scenario_type,
            scenario=scenarios[-2],
            image='tolindenba/ytsaurus:python-3.10',
            error_message=None,
            env_vars={},
            container_start_timeout=300,
            max_num_chars_bash_output=60000,
            bash_timeout=180,
        )

        client = IdeFormerClient(
            ideformer_host=os.environ['IDEFORMER_HOST'],
            ideformer_port=80,
            grazie_jwt_token=os.environ["IDEFORMER_JWT_TOKEN"],
            client_auth_type=AuthType.APPLICATION,
            client_auth_version=AuthVersion.V5,
            client_agent_name="vcs-agent",  # can be any
            client_agent_version="dev",  # can be any
        )

        system_prompt = dedent("""
            You MUST follow the instructions for answering:
            - You are an agent which can operate with the command line and change the file system.
            - You need to execute the given task with the best quality.
            - I have no fingers and the placeholders trauma. Return the entire code template for an answer when needed. NEVER use placeholders.
            - You ALWAYS will be PENALIZED for wrong and low-effort answers.
            - I'm going to tip $1,000,000 for the best reply.
            - Your answer is critical for my career.
            - YOU MUST USE THE PROVIDED TOOLS TO ACTUALLY CHANGE THE FILE SYSTEM.
            """)

        user_prompt_chunking = ('In the staging area of the git repository within the current directory you will find a file'
                       'with some staged changes. I want you to iteratively commit these changes as logically coherent'
                       'and cohesive as possible. Base your decisions on Clean Code principles, design patterns and system design '
                       'and act as a staff senior software engineer would. Create these commits in the "demo" branch and show'
                       'me the git log of only the branch and commits you created.')
        user_prompt_rebase = ('Clean up the commit history of the current Git branch. Focus on the last n commits, '
                              'starting from the current state up to the commit "68e876ee". Rebase interactively to reduce the '
                              'total number of commits to k, where k<n. Squash or regroup related commits, ensuring each '
                              'remaining commit represents a distinct, logical change. Eliminate redundant or trivial commits'
                              ' where possible, and ensure commit messages are clear and meaningful. After the rebase, '
                              'verify that the resulting commit history is concise, readable, and free of conflicts.'
                              'Use the exact commits specified and pay attention to use the correct hashes.'
                              )

        runner = IdeFormerSimpleGrazieChatRunner(
            system_prompt=system_prompt,
            user_prompt=user_prompt_rebase,
            client=client,
            tools_implementation_provider=tool,
            profile=Profile.OPENAI_GPT_4_O.name,
            max_tokens_to_sample=256,
            temperature=1.0,
            max_agent_iterations=2,
        )

        await runner.arun()

if __name__ == '__main__':
    asyncio.run(main())