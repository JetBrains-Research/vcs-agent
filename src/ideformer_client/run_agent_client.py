import asyncio
import logging
import os

from grazie.api.client.profiles import Profile
from grazie.cloud_tools_v2.authorization import AuthType, AuthVersion
from grazie.common.core.log import setup_logging
from ideformer.client.agents.simple_grazie_chat_runner import IdeFormerSimpleGrazieChatRunner
from ideformer.client.client import IdeFormerClient

from src.ideformer_client.data.PromptProvider import PromptProvider
from src.ideformer_client.environment.docker_manager import DockerManager
from src.ideformer_client.data.git_dataset_provider import GitDatasetProvider
from src.ideformer_client.data.yt_connection_manager import YTConnectionManager
from src.ideformer_client.environment.scenario_environment_manager import ScenarioEnvironmentManager
from src.ideformer_client.exceptions import ScenarioPreconditionSetupException
from src.ideformer_client.scenario_type import ScenarioType
from src.ideformer_client.terminal_access_tool_provider import TerminalAccessToolImplementationProvider


async def main():
    setup_logging(log_to_stderr=False, level=logging.INFO)

    yt_connection_manager = YTConnectionManager(dataset_table_location=os.environ['YT_DATASET_TABLE_LOCATION'])
    response = yt_connection_manager.get_dataset_stream()
    git_dataset_provider = GitDatasetProvider(response)

    i = 0

    docker_manager = DockerManager(
        image='tolindenba/ytsaurus:python-3.10',
        env_vars={},
        container_start_timeout=300,
    )
    docker_manager.setup_image()
    docker_manager.create_container()
    container = docker_manager.start_container()

    for repository in git_dataset_provider.stream_repositories():
        scenario_type: ScenarioType = ScenarioType.FILE_COMMIT_GRAM_REBASE # TODO iterate or pass as cmd arg?
        scenarios = git_dataset_provider.get_scenarios_for(scenario_type=scenario_type)

        for scenario in scenarios:
            # Ensure that we actually have > 0 scenarios of scenario_type for the current repository
            if len(scenarios) == 0:
                continue

            try:
                scenario_environment_manager = ScenarioEnvironmentManager(
                    container=container,
                    repository=repository,
                    scenario_type=scenario_type,
                    scenario=scenario,
                )
                scenario_environment_manager.clone_repository()
                scenario_environment_manager.setup_scenario_preconditions()
            except ScenarioPreconditionSetupException as e:
                logging.error(f"Skipping scenario {repository} due to precondition setup error: \n{e}")
                continue
            except ValueError as e:
                logging.error(f"Skipping scenario {repository} due to precondition setup error: \n{e}")
                continue

            system_prompt = PromptProvider.get_system_prompt()
            user_prompt = PromptProvider.get_prompt_for(scenario_type)

            tool = TerminalAccessToolImplementationProvider(
                container=container,
                error_message=None,
                max_num_chars_bash_output=30000,
                bash_timeout=180,
                workdir=scenario_environment_manager.repository_work_dir
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

            runner = IdeFormerSimpleGrazieChatRunner(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                client=client,
                tools_implementation_provider=tool,
                profile=Profile.OPENAI_GPT_4_O_MINI.name,
                max_tokens_to_sample=256,
                temperature=1.0,
                max_agent_iterations=1,
            )

            await runner.arun()
            break
        i += 1
        if i > 0:
            break

    docker_manager.stop_and_remove_container()

if __name__ == '__main__':
    asyncio.run(main())