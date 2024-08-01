import yt.wrapper as yt
from yt.wrapper.schema import TableSchema

import pandas as pd
import os

from schemas import RepositoryDataRow

yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"])
path_to_data = os.path.join(os.getcwd(), 'data')

input_dfs = []
for input_file in ['kotlin_repos.csv', 'java_repos.csv', 'python_repos.csv']:
    df = pd.read_csv(os.path.join(path_to_data, input_file))
    df['programmingLanguage'] = input_file.split('_')[0]
    input_dfs.append(df)

df = pd.concat(input_dfs, ignore_index=True)

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