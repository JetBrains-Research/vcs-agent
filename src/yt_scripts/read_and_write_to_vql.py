import os
import yt.wrapper as yt


def mapper_fun(input_row):
    input_row['content'] = 'lol'
    yield input_row


@yt.respawn_in_docker("docker.io/library/python:3.10.12")
def main():
    yt_client = yt.YtClient(proxy=os.environ["YT_PROXY"], token=os.environ["YT_TOKEN"])

    src_table = "//home/ml4se/tobias_lindenbauer/data/demo_repositories_to_scrape"
    dst_table = "//home/ml4se/tobias_lindenbauer/data/demo_scraper_output"

    yt_client.run_map(
        mapper_fun,
        src_table,
        dst_table,
        job_count=3,
        spec={
            "mapper": {
                "docker_image": "docker.io/library/python:3.10.12",
            }
        },
        format=yt.YsonFormat(require_yson_bindings=False)
    )


if __name__ == '__main__':
    main()
