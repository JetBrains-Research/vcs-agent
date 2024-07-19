import os
import yt.wrapper as yt
from mapper import DummyMapper

yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"])


def main():
    src_table = "//home/ml4se/tobias_lindenbauer/data/demo_repositories_to_scrape"
    dst_table = "//home/ml4se/tobias_lindenbauer/data/demo_scraper_output"

    yt.run_map(DummyMapper(),
               [src_table],
               [dst_table],
               job_count=3,
               spec={
                   "mapper": {
                       "docker_image": "docker.io/library/python:3.10",
                   }
               })


if __name__ == '__main__':
    main()
