"""
RAG evaluation harness — 500-query golden dataset CI gate.

Evaluates retrieval quality against a golden dataset and fails if
accuracy drops more than 2% below the baseline.

Usage:
    # Run evaluation (requires running API stack)
    python eval/rag_eval.py --api-url http://localhost:8000 --api-key dev-api-key

    # Set baseline from current results
    python eval/rag_eval.py --set-baseline

    # CI mode (exits 1 if accuracy drop > 2%)
    python eval/rag_eval.py --ci --baseline eval/baseline.json

Metrics computed:
    hit_rate@k    — fraction of queries where a golden doc appears in top-k results
    mrr@k         — mean reciprocal rank of the first golden doc hit
    ndcg@k        — normalised discounted cumulative gain
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Optional

import httpx


# ---------------------------------------------------------------------------
# Evaluation metrics
# ---------------------------------------------------------------------------

def hit_rate(retrieved_ids: list[str], golden_ids: set[str], k: int = 5) -> float:
    return int(bool(set(retrieved_ids[:k]) & golden_ids))


def reciprocal_rank(retrieved_ids: list[str], golden_ids: set[str]) -> float:
    for i, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in golden_ids:
            return 1.0 / i
    return 0.0


def ndcg(retrieved_ids: list[str], golden_ids: set[str], k: int = 5) -> float:
    gains = [1.0 if doc_id in golden_ids else 0.0 for doc_id in retrieved_ids[:k]]
    dcg   = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted(gains, reverse=True)
    idcg  = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

def retrieve(api_url: str, api_key: str, query: str, top_k: int = 5) -> list[str]:
    """Call the chat endpoint in JSON mode and extract source document IDs."""
    import uuid
    payload = {
        "session_id": f"eval-{uuid.uuid4()}",
        "message":    query,
        "stream":     False,
    }
    resp = httpx.post(
        f"{api_url}/api/v1/chat",
        json=payload,
        headers={"X-API-Key": api_key},
        timeout=30.0,
    )
    resp.raise_for_status()
    sources = resp.json().get("sources", [])
    return [s["document_id"] for s in sources[:top_k]]


# ---------------------------------------------------------------------------
# Evaluation loop
# ---------------------------------------------------------------------------

def evaluate(
    dataset_path: Path,
    api_url: str,
    api_key: str,
    k: int = 5,
    max_queries: Optional[int] = None,
) -> dict:
    dataset = [json.loads(line) for line in dataset_path.read_text().splitlines() if line.strip()]
    if max_queries:
        dataset = dataset[:max_queries]

    hit_rates, rrs, ndcgs = [], [], []
    errors = 0

    for i, item in enumerate(dataset):
        query      = item["query"]
        golden_ids = set(item["golden_document_ids"])

        try:
            retrieved = retrieve(api_url, api_key, query, k)
            hit_rates.append(hit_rate(retrieved, golden_ids, k))
            rrs.append(reciprocal_rank(retrieved, golden_ids))
            ndcgs.append(ndcg(retrieved, golden_ids, k))
        except Exception as exc:
            print(f"  [ERROR] query {i}: {exc}", file=sys.stderr)
            errors += 1
            hit_rates.append(0.0)
            rrs.append(0.0)
            ndcgs.append(0.0)

        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(dataset)} queries evaluated …")

    n = len(dataset)
    return {
        f"hit_rate@{k}": sum(hit_rates) / n,
        "mrr":            sum(rrs)       / n,
        f"ndcg@{k}":      sum(ndcgs)    / n,
        "error_rate":     errors         / n,
        "n_queries":      n,
        "k":              k,
        "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# CI gate
# ---------------------------------------------------------------------------

GATE_METRICS = ["hit_rate@5", "mrr", "ndcg@5"]
MAX_DROP     = 0.02   # 2 percentage-point drop triggers failure


def check_regression(results: dict, baseline: dict) -> list[str]:
    failures = []
    for metric in GATE_METRICS:
        current  = results.get(metric, 0.0)
        base_val = baseline.get(metric, 0.0)
        drop     = base_val - current
        if drop > MAX_DROP:
            failures.append(
                f"{metric}: {current:.4f} vs baseline {base_val:.4f} "
                f"(drop {drop:.4f} > {MAX_DROP})"
            )
    return failures


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="ConvoAI RAG evaluation harness")
    parser.add_argument("--api-url",      default="http://localhost:8000")
    parser.add_argument("--api-key",      default="dev-api-key")
    parser.add_argument("--dataset",      default="eval/golden_dataset.jsonl")
    parser.add_argument("--baseline",     default="eval/baseline.json")
    parser.add_argument("--k",            type=int, default=5)
    parser.add_argument("--max-queries",  type=int, default=None)
    parser.add_argument("--set-baseline", action="store_true")
    parser.add_argument("--ci",           action="store_true", help="Exit 1 on regression")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Evaluating RAG quality against {dataset_path} …")
    results = evaluate(
        dataset_path=dataset_path,
        api_url=args.api_url,
        api_key=args.api_key,
        k=args.k,
        max_queries=args.max_queries,
    )

    print("\n=== Results ===")
    for key, val in results.items():
        if isinstance(val, float):
            print(f"  {key}: {val:.4f}")
        else:
            print(f"  {key}: {val}")

    if args.set_baseline:
        Path(args.baseline).write_text(json.dumps(results, indent=2))
        print(f"\nBaseline saved to {args.baseline}")
        return

    if args.ci:
        baseline_path = Path(args.baseline)
        if not baseline_path.exists():
            print("No baseline file found — skipping regression check.", file=sys.stderr)
            return
        baseline = json.loads(baseline_path.read_text())
        failures = check_regression(results, baseline)
        if failures:
            print("\n[FAIL] RAG quality regression detected:", file=sys.stderr)
            for f in failures:
                print(f"  • {f}", file=sys.stderr)
            sys.exit(1)
        else:
            print("\n[PASS] No regression detected.")


if __name__ == "__main__":
    main()
