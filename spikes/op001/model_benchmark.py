from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

import psutil
import torch
from transformers import AutoConfig, AutoModel, AutoModelForSequenceClassification, PreTrainedTokenizerFast


TEXTS = [
    "Superset 定时报表没有按计划发送。",
    "The Celery worker is unavailable and the scheduled report did not run.",
    "用户可以打开仪表盘，但无法访问底层数据集。",
    "Database connection validation timed out.",
]
PAIRS = [
    (TEXTS[0], "检查报告调度、Worker、Beat 和 Redis 的运行状态。"),
    (TEXTS[0], "修改仪表盘的颜色主题。"),
    (TEXTS[2], "检查用户角色及数据集权限。"),
    (TEXTS[3], "检查数据库地址、凭据和网络可达性。"),
]


def load_fast_tokenizer(path: Path, max_length: int) -> tuple[PreTrainedTokenizerFast, Path]:
    tokenizer_path = path / "tokenizer.json"
    if not tokenizer_path.is_file():
        fallback_dir = path.parent / "bge-m3"
        tokenizer_path = fallback_dir / "tokenizer.json"
        if not tokenizer_path.is_file() or sha256(path / "sentencepiece.bpe.model") != sha256(
            fallback_dir / "sentencepiece.bpe.model"
        ):
            raise RuntimeError("No compatible fast tokenizer JSON is available")
    tokenizer = PreTrainedTokenizerFast(
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
    return tokenizer, tokenizer_path


def load_legacy_bin_model(
    path: Path, classifier: bool = False
) -> tuple[torch.nn.Module, PreTrainedTokenizerFast, Path, list[str]]:
    """Load legacy .bin weights without Transformers' crashing Windows fast path."""
    config = AutoConfig.from_pretrained(path, trust_remote_code=False)
    model_class = AutoModelForSequenceClassification if classifier else AutoModel
    print("constructing model structure", file=sys.stderr, flush=True)
    model = model_class.from_config(config, trust_remote_code=False)
    print("reading legacy weights without mmap", file=sys.stderr, flush=True)
    state_dict = torch.load(
        path / "pytorch_model.bin",
        map_location="cpu",
        weights_only=True,
        mmap=False,
    )
    print("injecting model weights", file=sys.stderr, flush=True)
    compatibility = model.load_state_dict(state_dict, strict=False)
    allowed_legacy_keys = {"roberta.embeddings.position_ids"} if classifier else set()
    unexpected_keys = set(compatibility.unexpected_keys)
    if compatibility.missing_keys or unexpected_keys - allowed_legacy_keys:
        raise RuntimeError(
            f"Incompatible checkpoint: missing={compatibility.missing_keys}, "
            f"unexpected={compatibility.unexpected_keys}"
        )
    print("model weights injected", file=sys.stderr, flush=True)
    del state_dict
    gc.collect()
    model.eval()
    print("loading fast tokenizer", file=sys.stderr, flush=True)
    tokenizer, tokenizer_path = load_fast_tokenizer(path, 512 if classifier else 8192)
    print("tokenizer loaded", file=sys.stderr, flush=True)
    return model, tokenizer, tokenizer_path, sorted(unexpected_keys)


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * ratio
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_inventory(path: Path) -> dict[str, Any]:
    files = [item for item in path.rglob("*") if item.is_file()]
    required = ["config.json", "pytorch_model.bin", "tokenizer_config.json"]
    return {
        "path": str(path),
        "file_count": len(files),
        "total_bytes": sum(item.stat().st_size for item in files),
        "required_files": {name: (path / name).is_file() for name in required},
        "config_sha256": sha256(path / "config.json"),
        "weights_bytes": (path / "pytorch_model.bin").stat().st_size,
    }


class PeakRss:
    def __init__(self) -> None:
        self._process = psutil.Process()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self.before = self._process.memory_info().rss
        self.peak = self.before

    def _sample(self) -> None:
        while not self._stop.wait(0.05):
            self.peak = max(self.peak, self._process.memory_info().rss)

    def __enter__(self) -> "PeakRss":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()
        self.peak = max(self.peak, self._process.memory_info().rss)


def timed_runs(operation: Callable[[], Any], runs: int = 7) -> tuple[list[float], Any]:
    output: Any = None
    durations: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        output = operation()
        durations.append((time.perf_counter() - started) * 1000)
    return durations, output


def embedding_benchmark(path: Path) -> tuple[torch.nn.Module, dict[str, Any]]:
    print(f"loading embedding model from {path}", file=sys.stderr, flush=True)
    started = time.perf_counter()
    model, tokenizer, tokenizer_path, ignored_keys = load_legacy_bin_model(path)
    load_seconds = time.perf_counter() - started

    def encode(texts: list[str]) -> torch.Tensor:
        inputs = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
        with torch.inference_mode():
            vectors = model(**inputs).last_hidden_state[:, 0]
            return torch.nn.functional.normalize(vectors, p=2, dim=1)

    print("running embedding warm-up", file=sys.stderr, flush=True)
    encode(TEXTS[:1])
    print("running embedding timed samples", file=sys.stderr, flush=True)
    durations, vectors = timed_runs(lambda: encode(TEXTS))
    return model, {
        "load_seconds": load_seconds,
        "batch_size": len(TEXTS),
        "runs": len(durations),
        "latency_ms": {
            "p50": statistics.median(durations),
            "p95": percentile(durations, 0.95),
            "samples": durations,
        },
        "pooling": "cls_token_from_local_1_Pooling_config",
        "tokenizer_source": str(tokenizer_path),
        "ignored_legacy_state_keys": ignored_keys,
        "output_dimension": int(vectors.shape[1]),
        "first_vector_norm": float(torch.linalg.vector_norm(vectors[0])),
    }


def reranker_benchmark(path: Path) -> tuple[torch.nn.Module, dict[str, Any]]:
    print(f"loading reranker model from {path}", file=sys.stderr, flush=True)
    started = time.perf_counter()
    model, tokenizer, tokenizer_path, ignored_keys = load_legacy_bin_model(path, classifier=True)
    load_seconds = time.perf_counter() - started

    def predict(pairs: list[tuple[str, str]]) -> torch.Tensor:
        inputs = tokenizer(
            [pair[0] for pair in pairs],
            [pair[1] for pair in pairs],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        with torch.inference_mode():
            return model(**inputs).logits.reshape(-1)

    predict(PAIRS[:1])
    durations, scores = timed_runs(lambda: predict(PAIRS))
    return model, {
        "load_seconds": load_seconds,
        "batch_size": len(PAIRS),
        "runs": len(durations),
        "latency_ms": {
            "p50": statistics.median(durations),
            "p95": percentile(durations, 0.95),
            "samples": durations,
        },
        "score_type": "raw_logit",
        "tokenizer_source": str(tokenizer_path),
        "ignored_legacy_state_keys": ignored_keys,
        "scores": [float(score) for score in scores],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("embedding", "reranker", "combined"))
    parser.add_argument("--embedding-path", type=Path, default=Path(os.getenv("EMBEDDING_MODEL_PATH", r"D:\Agent\models\bge-m3")))
    parser.add_argument("--reranker-path", type=Path, default=Path(os.getenv("RERANKER_MODEL_PATH", r"D:\Agent\models\bge-reranker-large")))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    torch.set_num_interop_threads(1)
    result: dict[str, Any] = {
        "mode": args.mode,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu": os.cpu_count(),
            "torch": torch.__version__,
            "torch_threads": torch.get_num_threads(),
            "device": "cpu",
            "inference_concurrency": 1,
            "checkpoint_loader": "explicit_non_mmap_legacy_bin",
        },
    }

    with PeakRss() as memory:
        if args.mode in {"embedding", "combined"}:
            result["embedding_inventory"] = model_inventory(args.embedding_path)
            embedding_model, result["embedding"] = embedding_benchmark(args.embedding_path)
        if args.mode in {"reranker", "combined"}:
            result["reranker_inventory"] = model_inventory(args.reranker_path)
            reranker_model, result["reranker"] = reranker_benchmark(args.reranker_path)
        # Keep references alive through the final memory sample in combined mode.
        locals().get("embedding_model")
        locals().get("reranker_model")

    print(f"completed {args.mode} benchmark", file=sys.stderr, flush=True)

    result["memory_bytes"] = {
        "rss_before": memory.before,
        "rss_peak": memory.peak,
        "rss_after": psutil.Process().memory_info().rss,
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
