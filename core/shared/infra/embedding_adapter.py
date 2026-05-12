from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    text: str
    vector: list[float]
    model: str
    dim: int


class EmbeddingAdapter(ABC):
    @abstractmethod
    def embed(self, text: str) -> EmbeddingResult:
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        ...

    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    def vector_dim(self) -> int:
        ...


class StubEmbeddingAdapter(EmbeddingAdapter):
    """테스트용 Stub — 결정적 가짜 벡터를 반환한다."""

    _DIM = 768

    def embed(self, text: str) -> EmbeddingResult:
        vector = [float(ord(c) % 10) / 10 for c in text[:self._DIM].ljust(self._DIM)]
        return EmbeddingResult(text=text, vector=vector, model="stub", dim=self._DIM)

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        return [self.embed(t) for t in texts]

    def model_name(self) -> str:
        return "stub"

    def vector_dim(self) -> int:
        return self._DIM
