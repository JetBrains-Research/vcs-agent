import os
import yt.wrapper as yt
from dataclasses import asdict
from yt.wrapper.schema import TableSchema

from src.yt_scripts.mappers import ErrorFilteringMapper

from src.yt_scripts.mappers import RepositoryDataMapper
from src.yt_scripts.schemas import RepositoryDataRow
import pandas as pd

def parse_table_into_dataframe(table_path: str) -> pd.DataFrame:
    dataset = yt.read_table_structured(table=table_path, row_type=RepositoryDataRow)

    return pd.DataFrame([asdict(row) for row in dataset])

def parse_table_into_csv_at(output_path: str, table_path: str):
    dataset_df = parse_table_into_dataframe(table_path)
    dataset_df.to_csv(output_path)

def remove_duplicates_in(table_path: str, yt_client: yt.YtClient):
    dataset_df = parse_table_into_dataframe(table_path)
    dataset_df.drop_duplicates(inplace=True)

    yt_client.remove(table_path)
    src_table_path = yt.TablePath(
        table_path,
        schema=TableSchema.from_row_type(RepositoryDataRow)
    )
    yt_client.write_table(
        table=src_table_path,
        input_stream=dataset_df.to_dict(orient="records"),
    )

def handle_errors_in_dataset(yt_client: yt.YtClient):
    src_table = "//home/ml4se/tobias_lindenbauer/data/scraper_output"
    dst_table = "//home/ml4se/tobias_lindenbauer/data/cleaned_scraper_output"
    dst_table_path = yt.TablePath(
        dst_table,
        schema=TableSchema.from_row_type(RepositoryDataRow)
    )
    yt_client.create('table', dst_table_path)

    yt_client.run_map(
        ErrorFilteringMapper(),
        source_table=src_table,
        destination_table=dst_table,
        job_count=10,

        # Specifying this aligns the python versions (apparently Nebius clusters run on 3.8 by default),
        # but Im pretty sure the YSON problem comes from the image not containing bindings.
        spec={
            "mapper": {
                "docker_image": "docker.io/liqsdev/ytsaurus:python-3.10",
                # Each job gets exactly one cpu, ensure high level of concurrency and efficient use of resources
                "cpu_limit": 1
            },
        },
    )

def run_repository_data_mapper(yt_client: yt.YtClient):
    src_table = "//home/ml4se/tobias_lindenbauer/data/repositories_to_scrape"
    dst_table = "//home/ml4se/tobias_lindenbauer/data/scraper_output"

    job_count = len(list(yt.read_table_structured(src_table, RepositoryDataRow)))

    yt_client.run_map(
        RepositoryDataMapper(sliding_window_size=3),
        src_table,
        dst_table,
        # Set to the amount of total repositories in src_table to enqueue individual repos and
        # spread the load evenly
        job_count=job_count,

        # Specifying this aligns the python versions (apparently Nebius clusters run on 3.8 by default),
        # but Im pretty sure the YSON problem comes from the image not containing bindings.
        spec={
            "mapper": {
                "docker_image": "docker.io/liqsdev/ytsaurus:python-3.10",
                # Each job can scale to at most 4 GiB of memory
                "memory_limit": 4 * 1024 ** 3,
                # The initial amount reserved for a job is thus 0.125 * 4000 = 500 MiB of memory
                "memory_reserve_factor": 0.125,
                # Support repositories up to a size of 1.5 GiB
                "tmpfs_size": 1500 * 1024 ** 2,
                "tmpfs_path": "repos",
                # Each job gets exactly one cpu, ensure high level of concurrency and efficient use of resources
                "cpu_limit": 1
            },
        },
    )


def main():
    yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"],
                            config={'pickling': {'ignore_system_modules': True}})
    # output_dir = os.path.join(os.getcwd(), 'data')
    remove_duplicates_in('//home/ml4se/tobias_lindenbauer/data/scraper_output', yt_client)

if __name__ == '__main__':
    main()