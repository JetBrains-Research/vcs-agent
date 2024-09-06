import os
import yt.wrapper as yt
from dataclasses import asdict

from src.yt_scripts.schemas import RepositoryDataRow
import pandas as pd

yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"],
                        config={'pickling': {'ignore_system_modules': True}})
dataset_table = "//home/ml4se/tobias_lindenbauer/data/scraper_output"

dataset = yt.read_table_structured(table=dataset_table, row_type=RepositoryDataRow)

dataset_df = pd.DataFrame([asdict(row) for row in dataset])
dataset_df.to_csv(os.path.join(os.getcwd(), 'data', 'scraped_raw_dataset.csv'))

