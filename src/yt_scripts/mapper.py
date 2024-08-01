from schemas import DummyRow
from typing import Iterable
import yt.wrapper


class DummyMapper(yt.wrapper.TypedJob):
    def __call__(self, row: DummyRow) -> Iterable[DummyRow]:
        yield DummyRow(content='I cannae belieeve eet')
