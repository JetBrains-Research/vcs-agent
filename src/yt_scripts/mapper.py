from schemas import DummyRow, RepositoryDataRow
from typing import Iterable
import yt.wrapper


class DummyMapper(yt.wrapper.TypedJob):
    def __call__(self, row: DummyRow) -> Iterable[DummyRow]:
        yield DummyRow(content='I cannae belieeve eet')


class RepositoryDataMapper(yt.wrapper.TypedJob):
    def __call__(self, row: RepositoryDataRow) -> Iterable[RepositoryDataRow]:
        row.scrapedData = '{dict of doom fear me}'
        yield row
