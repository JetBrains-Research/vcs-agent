import os
import sys

from schemas import DummyRow, RepositoryDataRow
from typing import Iterable
import yt.wrapper as yt

from git import Repo
import traceback

from src.repository_data_scraper import RepositoryDataScraper
from src.programming_language import ProgrammingLanguage


class DummyMapper(yt.TypedJob):
    def __call__(self, row: DummyRow) -> Iterable[DummyRow]:
        yield DummyRow(content='I cannae belieeve eet')


class RepositoryDataMapper(yt.TypedJob):
    def __call__(self, row: RepositoryDataRow) -> Iterable[RepositoryDataRow]:
        repository_path = "__".join(row.name.split("/"))

        try:
            repo_instance = Repo.clone_from(f'https://github.com/{row.name}.git',
                                            f'{repository_path}')

            os.chdir(repository_path)

            if row.programming_language == 'kotlin':
                programming_language = ProgrammingLanguage.KOTLIN
            elif row.programming_language == 'java':
                programming_language = ProgrammingLanguage.JAVA
            elif row.programming_language == 'python':
                programming_language = ProgrammingLanguage.PYTHON
            else:
                raise ValueError(f'Could not parse programming language: {row.programming_language}'
                                 '. Supported values: "kotlin", "java", "python"')

            repo_scraper = RepositoryDataScraper(repository=repo_instance,
                                                 programming_language=programming_language,
                                                 repository_name=row.name,
                                                 sliding_window_size=3)  # TODO hardcoded; Reduced sliding window size to 3

            repo_scraper.scrape()
            print(repo_scraper.accumulator, file=sys.stderr)

            row.file_commit_gram_scenarios = str(repo_scraper.accumulator['file_commit_gram_scenarios'])
            row.merge_scenarios = str(repo_scraper.accumulator['merge_scenarios'])
            row.cherry_pick_scenarios = str(repo_scraper.accumulator['cherry_pick_scenarios'])
        except Exception as e:
            row.error = traceback.format_exc()
            yield row  # Note that the column scrapedData could be empty here
        finally:
            yield row

