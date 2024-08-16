import yt.wrapper as yt
from yt.wrapper.schema import TableSchema

import pandas as pd
import os
import re

from schemas import RepositoryDataRow


def camel_to_snake(name: str) -> str:
    """
    Converts a camel-case string to snake_case.

    Parameters:
        name (str): The camel-case string to convert.

    Returns:
        str: The converted snake-case string.

    Example:
        >>> camel_to_snake('camelToSnake')
        'camel_to_snake'
        >>> camel_to_snake('lastCommitSHA')
        'last_commit_sha'
    """
    name = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)

    # Handle the case where a string has an acronym (e.g., 'SHA' in 'lastCommitSHA')
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    return name.lower()


yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"])
path_to_data = os.path.join(os.getcwd(), 'data')

input_dfs = []
for input_file in ['kotlin_repos.csv', 'java_repos.csv', 'python_repos.csv']:
    df = pd.read_csv(os.path.join(path_to_data, input_file))
    df['programmingLanguage'] = input_file.split('_')[0]
    input_dfs.append(df)

df = pd.concat(input_dfs, ignore_index=True)
# Convert all column names to snake case
df.columns = [camel_to_snake(col) for col in df.columns]

# Ensure missing values in UTF-8 objects are encoded as "None" instead of nan from float.
object_columns = list(df.select_dtypes(include=[object]).columns)
df[object_columns] = df[object_columns].replace(float('nan'), None)

# Create input table
src_table = "//home/ml4se/tobias_lindenbauer/data/repositories_to_scrape"
src_table_path = yt.TablePath(
    src_table,
    schema=TableSchema.from_row_type(RepositoryDataRow)
)

yt_client.write_table(
    table=src_table_path,
    input_stream=df.to_dict(orient="records"),
)

# Create output table
dst_table = "//home/ml4se/tobias_lindenbauer/data/scraper_output"
dst_table_path = yt.TablePath(
    dst_table,
    schema=TableSchema.from_row_type(RepositoryDataRow)
)

yt_client.create('table', dst_table_path)