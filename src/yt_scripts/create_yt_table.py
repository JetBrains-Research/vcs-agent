import yt.wrapper as yt
import yt.type_info as ti
import pandas as pd
import os

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
    schema=yt.schema.TableSchema()
    .add_column("id", ti.Optional[ti.Int64])
    .add_column("name", ti.Optional[ti.Utf8])
    .add_column("isFork", ti.Optional[ti.Bool])
    .add_column("commits", ti.Optional[ti.Int64])
    .add_column("branches", ti.Optional[ti.Int64])
    .add_column("releases", ti.Optional[ti.Int64])
    .add_column("forks", ti.Optional[ti.Int64])
    .add_column("mainLanguage", ti.Optional[ti.Utf8])
    .add_column("defaultBranch", ti.Optional[ti.Utf8])
    .add_column("license", ti.Optional[ti.Utf8])
    .add_column("homepage", ti.Optional[ti.Utf8])
    .add_column("watchers", ti.Optional[ti.Int64])
    .add_column("stargazers", ti.Optional[ti.Int64])
    .add_column("contributors", ti.Optional[ti.Int64])
    .add_column("size", ti.Optional[ti.Int64])
    .add_column("createdAt", ti.Optional[ti.String])
    .add_column("pushedAt", ti.Optional[ti.String])
    .add_column("updatedAt", ti.Optional[ti.String])
    .add_column("totalIssues", ti.Optional[ti.Double])
    .add_column("openIssues", ti.Optional[ti.Double])
    .add_column("totalPullRequests", ti.Optional[ti.Double])
    .add_column("openPullRequests", ti.Optional[ti.Double])
    .add_column("blankLines", ti.Optional[ti.Double])
    .add_column("codeLines", ti.Optional[ti.Double])
    .add_column("commentLines", ti.Optional[ti.Double])
    .add_column("metrics", ti.Optional[ti.Utf8])
    .add_column("lastCommit", ti.Optional[ti.Utf8])
    .add_column("lastCommitSHA", ti.Optional[ti.Utf8])
    .add_column("hasWiki", ti.Optional[ti.Bool])
    .add_column("isArchived", ti.Optional[ti.Bool])
    .add_column("isDisabled", ti.Optional[ti.Bool])
    .add_column("isLocked", ti.Optional[ti.Bool])
    .add_column("languages", ti.Optional[ti.Utf8])
    .add_column("labels", ti.Optional[ti.Utf8])
    .add_column("topics", ti.Optional[ti.Utf8])
    .add_column("programmingLanguage", ti.Optional[ti.Utf8])
    .add_column("scrapedData", ti.Optional[ti.Utf8])
)

yt_client.write_table(
    dst_table_path,
    df.to_dict(orient="records"),
)