import os
import shutil, stat
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


def on_rm_error(func, path, exc_info):
    """
    This method is called by the shutil.rmtree() function when it encounters an error while trying to remove a directory
     or a file. It is used to handle the error and continue with the removal operation.

    Parameters:
    - func: A function object that represents the removal function to be called again for the specific path.
        It should accept a single parameter, which is the path to be removed.
    - path: A string that represents the path of the directory or file that encountered the error.
    - exc_info: Unused by the implementation.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


class RepositoryDataMapper(yt.TypedJob):
    def __call__(self, row: RepositoryDataRow) -> Iterable[RepositoryDataRow]:
        repository_folder = "__".join(row.name.split("/"))
        path_to_repository = os.path.join('/slot/sandbox/repos', repository_folder)
        try:
            repo_instance = Repo.clone_from(f'https://github.com/{row.name}.git',
                                            f'{path_to_repository}')

            os.chdir(path_to_repository)
            print(os.getcwd(), file=sys.stderr)

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

            row.file_commit_gram_scenarios = str(repo_scraper.accumulator['file_commit_gram_scenarios'])
            row.merge_scenarios = str(repo_scraper.accumulator['merge_scenarios'])
            row.cherry_pick_scenarios = str(repo_scraper.accumulator['cherry_pick_scenarios'])

            # Move back into tmpfs working directrory
            os.chdir('..')

            print('Current working directory: '+os.getcwd(), file=sys.stderr)
            print(os.listdir('.'), file=sys.stderr)

            shutil.rmtree(repository_folder, onerror=on_rm_error)

            print(os.listdir('.'), file=sys.stderr)
        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            row.error = traceback.format_exc()
            yield row  # Note that the column scrapedData could be empty here
        finally:
            yield row

