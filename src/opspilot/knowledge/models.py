"""CPU-only, on-demand BGE-M3 and reranker adapters with the OP-001 Windows fallback."""

from __future__ import annotations

import gc
import hashlib
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from opspilot.knowledge.contracts import Embedding


class Encoder(Protocol):
    """The small interface used by ingestion and retrieval; it permits deterministic tests."""

    dense_version: str
    sparse_version: str

    def encode(self, texts: Sequence[str]) -> tuple[Embedding, ...]: ...


class Reranker(Protocol):
    """Optional reranking remains outside mandatory recall paths."""

    def score(self, query: str, passages: Sequence[str]) -> tuple[float, ...]: ...


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _WindowsModelLoader:
    """Copies the tested OP-001 loader semantics, not its spike module or control code."""

    @staticmethod
    def load(path: Path, *, classifier: bool) -> tuple[Any, Any]:
        import torch
        from transformers import AutoConfig, AutoModel, AutoModelForSequenceClassification

        tokenizer = _WindowsModelLoader.tokenizer(path, 512 if classifier else 8192)
        config = AutoConfig.from_pretrained(path, trust_remote_code=False)
        model_class: Any = AutoModelForSequenceClassification if classifier else AutoModel
        model = model_class.from_config(config, trust_remote_code=False)
        # SentencePiece crashes on this Windows setup and mmap triggers a native failure.
        state_dict = torch.load(
            path / "pytorch_model.bin", map_location="cpu", weights_only=True, mmap=False
        )
        compatibility = model.load_state_dict(state_dict, strict=False)
        allowed = {"roberta.embeddings.position_ids"} if classifier else set()
        if compatibility.missing_keys or set(compatibility.unexpected_keys) - allowed:
            raise RuntimeError(
                "local BGE checkpoint is incompatible with its declared architecture"
            )
        del state_dict
        gc.collect()
        model.eval()
        return model, tokenizer

    @staticmethod
    def tokenizer(path: Path, max_length: int) -> Any:
        from transformers import PreTrainedTokenizerFast

        tokenizer_path = path / "tokenizer.json"
        if not tokenizer_path.is_file():
            fallback = path.parent / "bge-m3" / "tokenizer.json"
            sentencepiece = path / "sentencepiece.bpe.model"
            fallback_piece = path.parent / "bge-m3" / "sentencepiece.bpe.model"
            if (
                not fallback.is_file()
                or not sentencepiece.is_file()
                or not fallback_piece.is_file()
            ):
                raise RuntimeError("no compatible fast tokenizer JSON is available")
            if _sha256(sentencepiece) != _sha256(fallback_piece):
                raise RuntimeError(
                    "fast-tokenizer fallback does not match the local SentencePiece model"
                )
            tokenizer_path = fallback
        return PreTrainedTokenizerFast(  # type: ignore[no-untyped-call]
            tokenizer_file=str(tokenizer_path),
            bos_token="<s>",
            cls_token="<s>",
            eos_token="</s>",
            sep_token="</s>",
            unk_token="<unk>",
            pad_token="<pad>",
            mask_token="<mask>",
            model_max_length=max_length,
        )


class BgeM3Encoder:
    """Serial BGE-M3 encoder with 1024-D CLS Dense and token-aware sparse weights.

    The locally verified checkpoint is an XLM-R encoder without a learned lexical head.
    Sparse values are therefore explicitly versioned as masked-token hidden-norm weights,
    rather than being represented as a fictional vendor-native lexical head.
    """

    dense_version = "bge-m3-cls-normalized-v1"
    sparse_version = "bge-m3-token-hidden-norm-v1"

    def __init__(self, model_path: str, *, max_length: int = 512) -> None:
        self._path = Path(model_path)
        self._max_length = max_length
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> tuple[Any, Any]:
        if self._model is None or self._tokenizer is None:
            if not self._path.is_dir():
                raise RuntimeError(f"BGE-M3 model directory does not exist: {self._path}")
            self._model, self._tokenizer = _WindowsModelLoader.load(self._path, classifier=False)
        return self._model, self._tokenizer

    def encode(self, texts: Sequence[str]) -> tuple[Embedding, ...]:
        if not texts:
            return ()
        import torch

        with self._lock:
            model, tokenizer = self._ensure_loaded()
            encoded = tokenizer(
                list(texts),
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            )
            with torch.inference_mode():
                hidden = model(**encoded).last_hidden_state
                dense = torch.nn.functional.normalize(hidden[:, 0], p=2, dim=1)
                token_norm = torch.linalg.vector_norm(hidden, dim=2)
            input_ids = encoded["input_ids"]
            attention = encoded["attention_mask"]
            results: list[Embedding] = []
            for row, vector in enumerate(dense):
                sparse: dict[str, float] = {}
                for token_id, active, value in zip(
                    input_ids[row], attention[row], token_norm[row], strict=True
                ):
                    if int(active) == 0:
                        continue
                    token = str(int(token_id))
                    sparse[token] = max(sparse.get(token, 0.0), float(value))
                results.append(
                    Embedding(
                        tuple(float(item) for item in vector),
                        sparse,
                        self.dense_version,
                        self.sparse_version,
                    )
                )
            return tuple(results)

    def close(self) -> None:
        """Release both large model references; the next request deliberately reloads them."""
        with self._lock:
            self._model = None
            self._tokenizer = None
            gc.collect()


class BgeRerankerLarge:
    """Optional serial CPU reranker, loaded only when a request enables it."""

    def __init__(self, model_path: str, *, max_length: int = 512) -> None:
        self._path = Path(model_path)
        self._max_length = max_length
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> tuple[Any, Any]:
        if self._model is None or self._tokenizer is None:
            if not self._path.is_dir():
                raise RuntimeError(f"BGE reranker directory does not exist: {self._path}")
            self._model, self._tokenizer = _WindowsModelLoader.load(self._path, classifier=True)
        return self._model, self._tokenizer

    def score(self, query: str, passages: Sequence[str]) -> tuple[float, ...]:
        if not passages:
            return ()
        import torch

        with self._lock:
            model, tokenizer = self._ensure_loaded()
            inputs = tokenizer(
                [query] * len(passages),
                list(passages),
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            )
            with torch.inference_mode():
                values = model(**inputs).logits.reshape(-1)
            return tuple(float(value) for value in values)

    def close(self) -> None:
        with self._lock:
            self._model = None
            self._tokenizer = None
            gc.collect()
