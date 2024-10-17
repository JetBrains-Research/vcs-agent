import ast
import os
import sys
from typing import List, Dict

import yt.wrapper as yt
from yt.wrapper.schema import TableSchema

from src.ideformer_client.scenario_type import ScenarioType
from src.yt_scripts.schemas import RepositoryDataRow

def get_scenario_at(scenario_index: int, scenarios: List) -> Dict:
    """
    Get the scenario at the specified index from the list of scenarios.

    Parameters:
    - scenario_index (int): The index of the desired scenario.
    - scenarios (List): A list of scenarios.

    Returns:
    - scenario (Dict): The scenario at the given index.

    Raises:
    - ValueError: If the scenario index is out of range.

    """
    if scenario_index < 0 or scenario_index >= len(scenarios):
        raise ValueError(f'Scenario index {scenario_index} is out of range.')

    return scenarios[scenario_index]


def unpack_scenario_for(scenario_type: ScenarioType, repository: RepositoryDataRow, scenario_index: int = None) -> Dict:
    """
    Unpacks a specific scenario for a given scenario type from a repository.

    Parameters:
    - scenario_type (ScenarioType): The type of scenario to unpack, must match the column name of the scenario type.
    - repository (RepositoryDataRow): The repository containing the scenarios.
    - scenario_index (int, optional): The index of the scenario to unpack. Defaults to None. If not passed, the first
        scenario is processed.

    Returns:
    - Dict: The unpacked scenario as a dictionary.

    Raises:
    - ValueError if the index is out of range or if the passed scenario_type is not valid.

    Examples:
    unpack_scenario_for('file_commit_gram_scenarios', repository_data_row, 1)

    """
    if scenario_index is None:
        print('No index passed, returning the first scenario (index=0).', file=sys.stderr)
        scenario_index = 0

    # Since there are two different setups based on the file_commit_gram_scenarios we need to cover both here
    # See the enum class and the scenario precondition setup in the TerminalAccessToolProvider
    if 'file_commit_gram_scenarios' in scenario_type.value:
        if repository.file_commit_gram_scenarios is None:
            print(f'No scenario of type: {scenario_type} available for repository: {repository.name}. Returning None.', file=sys.stderr)
            return {}
        else:
            scenarios = ast.literal_eval(repository.file_commit_gram_scenarios)
            return get_scenario_at(scenario_index, scenarios)
    elif scenario_type is ScenarioType.MERGE:
        if repository.merge_scenarios is None:
            print(f'No scenario of type: {scenario_type} available for repository: {repository.name}. Returning None.', file=sys.stderr)
            return {}
        else:
            scenarios = ast.literal_eval(repository.merge_scenarios)
            # TODO: It is quite inefficient to parse all scenarios just to return only a single one
            return get_scenario_at(scenario_index, scenarios)
    elif scenario_type is ScenarioType.CHERRY_PICK:
        if repository.cherry_pick_scenarios is None:
            print(f'No scenario of type: {scenario_type} available for repository: {repository.name}. Returning empty dict.', file=sys.stderr)
            return {}
        else:
            scenarios = ast.literal_eval(repository.cherry_pick_scenarios)
            return get_scenario_at(scenario_index, scenarios)
    else:
        raise ValueError('Invalid scenario type. For valid types check the documentation of this function.')


def main():
    # Create input table
    dataset_table = "//home/ml4se/tobias_lindenbauer/data/scraper_output"
    dataset_table_path = yt.TablePath(
        dataset_table,
        schema=TableSchema.from_row_type(RepositoryDataRow)
    )

    response = yt.read_table_structured(table=dataset_table_path, row_type=RepositoryDataRow)

    x = unpack_scenario_for(ScenarioType.FILE_COMMIT_GRAM_CHUNK, next(iter(response)), 1)
    print(x)


if __name__ == '__main__':
    main()