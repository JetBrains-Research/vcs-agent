from multiprocessing.managers import Value

from yt.wrapper.response_stream import ResponseStream

from src.ideformer_client.scenario_type import ScenarioType
from src.yt_scripts.schemas import RepositoryDataRow

import sys
import ast

from typing import Dict, Generator


class GitDatasetProvider:
    """
        Abstraction for interactions with the dataset. Provides functionality to iterate over the dataset and retrieve
        the scenarios of a repository.
    """

    def __init__(self, record_response_stream: ResponseStream):
        self.dataset_stream = record_response_stream
        self.current_repository = None

    def stream_repositories(self) -> Generator[RepositoryDataRow, None, None]:
        """
        Streams repository data rows from the dataset. Before yielding self.current_repository is updated to the
        current repository.

        Returns:
            Generator: A generator for RepositoryDataRow objects.

        Yields:
            RepositoryDataRow: A data row representing a repository from the dataset.
        """
        for repository in self.dataset_stream:
            self.current_repository = repository
            yield repository

    def get_scenarios_for(self, scenario_type: ScenarioType) -> Dict:
        """
        Returns all scenarios of the specified scenario_type from the current repository as a dict.

        Within the dataset the scenarios are stored as raw text, this means this function also parses the scenarios
        from string to Python dictionaries. We thus advise to only call this function once per scenario_type and repository.

        Parameters:
            scenario_type (ScenarioType): The type of scenarios to return.

        Raises:
            ValueError if called with a ScenarioType that is not defined in the ScenarioType enum class.

        Returns:
            Dict: The scenarios of scenario_type as a dictionary.
        """
        # Since there are two different setups based on the file_commit_gram_scenarios we need to cover both here
        # See the enum class and the scenario precondition setup in the TerminalAccessToolProvider
        if 'file_commit_gram_scenarios' in scenario_type.value:
            if self.current_repository.file_commit_gram_scenarios is None:
                print(
                    f'No scenario of type: {scenario_type} available for repository: {self.current_repository.name}. Returning None.',
                    file=sys.stderr)
                return {}
            else:
                return ast.literal_eval(self.current_repository.file_commit_gram_scenarios)
        elif scenario_type is ScenarioType.MERGE:
            if self.current_repository.merge_scenarios is None:
                print(
                    f'No scenario of type: {scenario_type} available for repository: {self.current_repository.name}. Returning None.',
                    file=sys.stderr)
                return {}
            else:
                return ast.literal_eval(self.current_repository.merge_scenarios)
        elif scenario_type is ScenarioType.CHERRY_PICK:
            if self.current_repository.cherry_pick_scenarios is None:
                print(
                    f'No scenario of type: {scenario_type} available for repository: {self.current_repository.name}. Returning empty dict.',
                    file=sys.stderr)
                return {}
            else:
                return ast.literal_eval(self.current_repository.cherry_pick_scenarios)
        else:
            raise ValueError('Invalid scenario type. For valid types check the ScenarioType enum class.')