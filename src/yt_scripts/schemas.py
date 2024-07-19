from yt.wrapper import yt_dataclass
from typing import Optional

@yt_dataclass
class DummyRow:
    content: str

@yt_dataclass
class RepositoryDataRow:
    id: int
    name: Optional[str]
    isFork: Optional[bool]
    commits: Optional[int]
    branches: Optional[int]
    releases: Optional[int]
    forks: Optional[int]
    mainLanguage: Optional[str]
    defaultBranch: Optional[str]
    license: Optional[str]
    homepage: Optional[str]
    watchers: Optional[int]
    stargazers: Optional[int]
    contributors: Optional[int]
    size: Optional[int]
    createdAt: Optional[str]
    pushedAt: Optional[str]
    updatedAt: Optional[str]
    totalIssues: Optional[float]
    openIssues: Optional[float]
    totalPullRequests: Optional[float]
    openPullRequests: Optional[float]
    blankLines: Optional[float]
    codeLines: Optional[float]
    commentLines: Optional[float]
    metrics: Optional[str]
    lastCommit: Optional[str]
    lastCommitSHA: Optional[str]
    hasWiki: Optional[bool]
    isArchived: Optional[bool]
    isDisabled: Optional[bool]
    isLocked: Optional[bool]
    languages: Optional[str]
    labels: Optional[str]
    topics: Optional[str]
    programmingLanguage: Optional[str]
    scrapedData: Optional[str]
