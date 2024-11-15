import asyncio
import logging
import os

from grazie.api.client.profiles import Profile
from grazie.cloud_tools_v2.authorization import AuthType, AuthVersion
from grazie.common.core.log import setup_logging
from ideformer.client.agents.simple_grazie_chat_runner import IdeFormerSimpleGrazieChatRunner
from ideformer.client.client import IdeFormerClient

from src.ideformer_client.data.prompt_provider import PromptProvider
from src.ideformer_client.environment.docker_manager import DockerManager
from src.ideformer_client.data.git_dataset_provider import GitDatasetProvider
from src.ideformer_client.data.yt_connection_manager import YTConnectionManager
from src.ideformer_client.environment.evaluator import Evaluator
from src.ideformer_client.environment.scenario_environment_manager import ScenarioEnvironmentManager
from src.ideformer_client.utils.exceptions import ScenarioEnvironmentException
from src.ideformer_client.environment.scenario_type import ScenarioType
from src.ideformer_client.environment.terminal_access_tool_provider import TerminalAccessToolImplementationProvider


async def main():
    setup_logging(log_to_stderr=False, level=logging.INFO)
    yt_connection_manager = YTConnectionManager(dataset_table_location=os.environ['YT_DATASET_TABLE_LOCATION'])
    response = yt_connection_manager.get_dataset_stream()
    git_dataset_provider = GitDatasetProvider(response)

    i = 0

    run_statistics = {'successes': {ScenarioType.FILE_COMMIT_GRAM_CHUNK.value: 0,
                        ScenarioType.FILE_COMMIT_GRAM_REBASE.value: 0,
                        ScenarioType.MERGE.value: 0,
                        ScenarioType.CHERRY_PICK.value: 0},
                      'totals': {ScenarioType.FILE_COMMIT_GRAM_CHUNK.value: 0,
                        ScenarioType.FILE_COMMIT_GRAM_REBASE.value: 0,
                        ScenarioType.MERGE.value: 0,
                        ScenarioType.CHERRY_PICK.value: 0}
                      }

    docker_manager = DockerManager(
        image='tolindenba/ytsaurus:python-3.10',
        env_vars={},
        container_start_timeout=300,
    )
    docker_manager.setup_image()
    docker_manager.create_container()
    container = docker_manager.start_container()

    for repository in git_dataset_provider.stream_repositories():
        scenario_type: ScenarioType = ScenarioType.FILE_COMMIT_GRAM_CHUNK # TODO iterate or pass as cmd arg?
        scenarios = git_dataset_provider.get_scenarios_for(scenario_type=scenario_type)
        j = 0

        try:
            scenario_environment_manager = ScenarioEnvironmentManager(
                container=container,
                repository=repository,
            )
            scenario_environment_manager.setup_repository()
        except ScenarioEnvironmentException as e:
            logging.error(f"Skipping scenario {repository}: \n{e}")
            continue
        except ValueError as e:
            logging.error(f"Skipping scenario {repository}. Could not set repository working directory: \n{e}")
            continue

        evaluator = Evaluator(container=container,
                              agent_target_branch_name=scenario_environment_manager.AGENT_TARGET_BRANCH_NAME,
                              repository_work_dir=scenario_environment_manager.repository_work_dir)
        for scenario_type in ScenarioType:
            k=0
            for scenario in scenarios:
                # Ensure that we actually have > 0 scenarios of scenario_type for the current repository
                if len(scenarios) == 0:
                    continue

                try:
                    scenario_environment_manager.set_scenario(scenario)
                    scenario_environment_manager.set_scenario_type(scenario_type)
                    scenario_environment_manager.setup_scenario_preconditions()
                except ScenarioEnvironmentException as e:
                    logging.error(f"Skipping scenario {repository} due to precondition setup error: \n{e}")
                    scenario_environment_manager.teardown_scenario()
                    continue

                system_prompt = PromptProvider.get_system_prompt()

                try:
                    scenario_context = scenario_environment_manager.provide_scenario_context()
                    user_prompt = PromptProvider.get_prompt_for(scenario_type, scenario, context=scenario_context,
                                                                agent_target_branch_name=ScenarioEnvironmentManager.AGENT_TARGET_BRANCH_NAME)
                except ScenarioEnvironmentException as e:
                    logging.error(f"Could not fetch scenario context for repository {repository.name}, scenario type "
                                  f"{scenario_type} and\nscenario{scenario}:\n{e}\n"
                                  'Proceeding without context.')
                    user_prompt = PromptProvider.get_prompt_for(scenario_type, scenario, context='unavailable',
                                                                agent_target_branch_name=ScenarioEnvironmentManager.AGENT_TARGET_BRANCH_NAME)

                logging.debug(f'Current scenario is given by:\nRepository: {repository.name}\nScenario type: {scenario_type}'
                              f'\nScenario: {scenario}\nUser prompt: {user_prompt}')

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

                # Evaluate
                evaluator.set_scenario(scenario)
                evaluator.set_scenario_type(scenario_type)
                if evaluator.evaluate():
                    logging.info('Yay, successfully resolved this scenario!')
                    run_statistics['successes'][scenario_type.value] += 1
                else:
                    logging.info('Could not resolve this scenario.')

                run_statistics['totals'][scenario_type.value] += 1

                try:
                    scenario_environment_manager.teardown_scenario()
                except ScenarioEnvironmentException as e:
                    logging.error(f"Scenario cleanup failed for {scenario}: \n{e}\n"
                                  f"Attempting to recover by removing and re-setting (incl. clone) the repository.")
                    try:
                        scenario_environment_manager.teardown_repository()
                        scenario_environment_manager.setup_repository()
                    except ScenarioEnvironmentException:
                        logging.error(f'Could not recover for scenario: {scenario} in repository {repository}. Continuing with the next repository.')
                        break
                # Limit to two scenarios
                k += 1
                if k> 1:
                    break

            # Limit to two scenario types
            j += 1
            if j > 1:
                break

        # If this raises an exception the only way out would be re-orchestrating the Docker container, or removing with force
        # Neither of which I really want to do for now.
        scenario_environment_manager.teardown_repository()

        # Limit to two repositories
        i += 1
        if i > 1:
            break

    print(run_statistics)

if __name__ == '__main__':
    asyncio.run(main())