import os
import yt.wrapper as yt

from mapper import RepositoryDataMapper


def main():
    yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"],
                            config={'pickling': {'ignore_system_modules': True}})

    src_table = "//home/ml4se/tobias_lindenbauer/data/repositories_to_scrape"
    dst_table = "//home/ml4se/tobias_lindenbauer/data/scraper_output"

    yt_client.run_map(
        RepositoryDataMapper(),
        src_table,
        dst_table,
        # Set to the amount of total repositories in src_table to enqueue individual repos and
        # spread the load evenly
        job_count=300,

        # Specifying this aligns the python versions (apparently Nebius clusters run on 3.8 by default),
        # but Im pretty sure the YSON problem comes from the image not containing bindings.
        spec={
            "mapper": {
                "docker_image": "docker.io/liqsdev/ytsaurus:python-3.10",
                # Each job can use at most 3 GiB of memory, the initial amount reserved for a job is thus
                # 0.075 * 3000 = 225 MiB of memory
                "memory_reserve_factor": 0.075,
                "memory_limit": 3 * 1024 ** 3,
                # Support repositories up to a size of 2 GiB
                "tmpfs_size": 2 * 1024 ** 3,
                "tmpfs_path": "repos",
                "cpu_limit": 30
            },
        },
    )


if __name__ == '__main__':
    main()
