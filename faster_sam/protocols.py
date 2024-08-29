from typing import Protocol, runtime_checkable

from faster_sam.schemas import SQSInfo


@runtime_checkable
class IntoSQSInfo(Protocol):
    def into(self) -> SQSInfo: ...
