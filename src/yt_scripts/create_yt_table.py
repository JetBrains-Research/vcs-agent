import yt.wrapper as yt
from yt.wrapper.schema import TableSchema

import pandas as pd
import os

from schemas import RepositoryDataRow

yt_client = yt.YtClient("neumann.yt.nebius.yt", token=os.environ["YT_TOKEN"])
path_to_data = os.path.join(os.getcwd(), 'data')

input_dfs = []
for input_file in ['kotlin_repos.csv', 'java_repos.csv', 'python_repos.csv']:
    df = pd.read_csv(os.path.join(path_to_data, input_file))
    df['programmingLanguage'] = input_file.split('_')[0]
    input_dfs.append(df)

df = pd.concat(input_dfs, ignore_index=True)
df['scrapedData'] = None

# Ensure missing values in UTF-8 objects are encoded as "None" instead of nan from float.
object_columns = list(df.select_dtypes(include=[object]).columns)
df[object_columns] = df[object_columns].replace(float('nan'), None)

dst_table = "//home/ml4se/tobias_lindenbauer/data/repositories_to_scrape"
dst_table_path = yt.TablePath(
    dst_table,
    schema=TableSchema.from_row_type(RepositoryDataRow)
)

yt_client.write_table(
    dst_table_path,
    df.to_dict(orient="records"),
)