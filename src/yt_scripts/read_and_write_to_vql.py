import os
import yt.wrapper as yt
from mapper import DummyMapper

def main():
    yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"])

    src_table = "//home/ml4se/tobias_lindenbauer/data/demo_repositories_to_scrape"
    dst_table = "//home/ml4se/tobias_lindenbauer/data/demo_scraper_output"

    yt_client.run_map(
        DummyMapper(),
        src_table,
        dst_table,
        job_count=3,
    )


if __name__ == '__main__':
    main()
