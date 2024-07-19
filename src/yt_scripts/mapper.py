from schemas import DummyRow
from typing import Iterable


class DummyMapper:
    def __call__(self, row: DummyRow) -> Iterable[DummyRow]:
        yield DummyRow(content='test text replacement')
