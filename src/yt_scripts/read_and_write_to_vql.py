import os
import yt.wrapper as yt

from mapper import RepositoryDataMapper

def main():
    yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"])

    src_table = "//home/ml4se/tobias_lindenbauer/data/repositories_to_scrape"
    dst_table = "//home/ml4se/tobias_lindenbauer/data/scraper_output"

    yt_client.run_map(
        RepositoryDataMapper(),
        src_table,
        dst_table,

        # Specifying this aligns the python versions (apparently Nebius clusters run on 3.8 by default),
        # but Im pretty sure the YSON problem comes from the image not containing bindings.
        spec={
            "mapper": {
                "docker_image": "docker.io/liqsdev/ytsaurus:python-3.10",
            }
        },
    )


if __name__ == '__main__':
    main()
