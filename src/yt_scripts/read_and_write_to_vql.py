import os
import yt.wrapper as yt

from mapper import RepositoryDataMapper
from schemas import RepositoryDataRow


def main():
    yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"],
                            config={'pickling': {'ignore_system_modules': True}})

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


if __name__ == '__main__':
    main()
