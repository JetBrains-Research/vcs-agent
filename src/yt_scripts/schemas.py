from yt.wrapper import yt_dataclass
from typing import Optional
from dataclasses import dataclass


@yt_dataclass
class DummyRow:
    content: str


@yt_dataclass
@dataclass
class RepositoryDataRow:
    id: int
    name: Optional[str]
    is_fork: Optional[bool]
    commits: Optional[int]
    branches: Optional[int]
    releases: Optional[int]
    forks: Optional[int]
    main_language: Optional[str]
    default_branch: Optional[str]
    license: Optional[str]
    homepage: Optional[str]
    watchers: Optional[int]
    stargazers: Optional[int]
    contributors: Optional[int]
    size: Optional[int]
    created_at: Optional[str]
    pushed_at: Optional[str]
    updated_at: Optional[str]
    total_issues: Optional[float]
    open_issues: Optional[float]
    total_pull_requests: Optional[float]
    open_pull_requests: Optional[float]
    blank_lines: Optional[float]
    code_lines: Optional[float]
    comment_lines: Optional[float]
    metrics: Optional[str]
    last_commit: Optional[str]
    last_commit_sha: Optional[str]
    has_wiki: Optional[bool]
    is_archived: Optional[bool]
    is_disabled: Optional[bool]
    is_locked: Optional[bool]
    languages: Optional[str]
    labels: Optional[str]
    topics: Optional[str]
    programming_language: Optional[str]
    file_commit_gram_scenarios: Optional[str]
    merge_scenarios: Optional[str]
    cherry_pick_scenarios: Optional[str]
    error: Optional[str]
