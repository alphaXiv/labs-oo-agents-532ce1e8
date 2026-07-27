"""Build the public evidence bundle and figures from terminal run logs.

Run with:
  uv run --with matplotlib python scripts/build_reproduction_assets.py --refresh

Without ``--refresh``, the script rebuilds figures from the committed compact
results file and does not require OpenResearch access.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "interface-reproduction"
DATA = OUT / "data" / "results.json"
IMAGES = OUT / "images"

SOURCES = {
    "json": {
        "label": "JSON tools",
        "branches": [
            "orx/kubernetes-toolchain-json-control",
            "orx/json-control-independent-seeds",
        ],
        "runs": [
            "c9618bc2-4211-467a-ad75-143472c3a616",
            "cc3340e9-fb7c-42c8-8c7e-21837c03fff1",
        ],
    },
    "nooa": {
        "label": "Typed live NOOA",
        "branches": [
            "orx/toolchain-round-nooa-live",
            "orx/nooa-live-independent-seeds",
            "orx/nooa-live-independent-seeds-b",
        ],
        "runs": [
            "47939711-9acd-4472-aff1-bb412adab978",
            "cb55ff7e-2749-4640-9ba1-00a54b655a41",
            "63f5344d-d7cc-459b-99ac-8929fea67566",
        ],
    },
    "nooa_no_validation": {
        "label": "NOOA, no validation",
        "branches": [
            "orx/validation-ablation-shard-a",
            "orx/validation-ablation-independent-seeds",
        ],
        "runs": [
            "f6e4ddbd-f7e7-4af2-9226-0c222c10900e",
            "8d2501a9-27cf-4032-81a9-12fb69e96627",
        ],
    },
    "nooa_serialized": {
        "label": "NOOA, serialized copies",
        "branches": [
            "orx/toolchain-round-nooa-serialized",
            "orx/serialized-copy-independent-seeds",
        ],
        "runs": [
            "4b273409-57d6-4048-a030-52368bc8bc76",
            "bb32402b-afe0-4262-a434-998aa32ee405",
        ],
    },
}

ORDER = ["json", "nooa", "nooa_no_validation", "nooa_serialized"]
COLORS = {
    "json": "#64748B",
    "nooa": "#76B900",
    "nooa_no_validation": "#F59E0B",
    "nooa_serialized": "#E45756",
}
FAMILY_ORDER = [
    "state_mutation",
    "reference_identity",
    "typed_nested_output",
    "error_recovery",
    "multi_step_tools",
]
FAMILY_LABELS = {
    "state_mutation": "State\nmutation",
    "reference_identity": "Reference\nidentity",
    "typed_nested_output": "Typed nested\noutput",
    "error_recovery": "Error\nrecovery",
    "multi_step_tools": "Multi-step\ntools",
}


def fetch_summary(run_id: str) -> dict:
    proc = subprocess.run(
        ["orx", "logs", run_id, "--bytes", "1000000"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"REPRO_RESULT_JSON=(\{.*\})", proc.stdout)
    if not match:
        raise RuntimeError(f"run {run_id} has no terminal REPRO_RESULT_JSON")
    return json.loads(match.group(1))


def compact_record(record: dict) -> dict:
    exception = record.get("exception")
    return {
        key: record[key]
        for key in [
            "harness",
            "family",
            "seed",
            "success",
            "failure_class",
            "model_calls",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "latency_s",
            "tool_errors",
            "validation_retries",
            "workspace",
        ]
    } | {"exception_type": exception.split(":", 1)[0] if exception else None}


def refresh_data() -> dict:
    conditions = {}
    for condition, source in SOURCES.items():
        summaries = [fetch_summary(run_id) for run_id in source["runs"]]
        records = [
            compact_record(record)
            for summary in summaries
            for record in summary["records"]
        ]
        conditions[condition] = {
            "label": source["label"],
            "branches": source["branches"],
            "run_ids": source["runs"],
            "run_wall_s": [summary["run_wall_s"] for summary in summaries],
            "records": records,
        }
    payload = {
        "schema_version": 1,
        "paper_id": "2607.20709",
        "model": "Qwen/Qwen3-30B-A3B-Instruct-2507",
        "backend": "kubernetes",
        "gpu_model": "NVIDIA RTX PRO 6000 Blackwell",
        "peak_concurrent_gpu_count": 16,
        "campaign_start": "2026-07-27T00:55:19Z",
        "first_kubernetes_launch": "2026-07-27T01:05:09Z",
        "campaign_end": "2026-07-27T02:04:28Z",
        "campaign_wall_hours": 1.1525,
        "sampling": {
            "temperature": 0.2,
            "top_p": 0.9,
            "max_turns": 6,
            "max_tokens": 1200,
        },
        "conditions": conditions,
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def mechanism_success(record: dict) -> bool:
    workspace = record["workspace"]
    if record["family"] == "state_mutation":
        return workspace["counter"] == 12 and workspace["journal"] == ["alpha", "beta"]
    if record["family"] == "reference_identity":
        return (
            workspace["aliases_share_identity"]
            and workspace["alias_a"]["label"] == "shared-green"
            and workspace["alias_b"]["label"] == "shared-green"
            and workspace["alias_a"]["touches"] == 1
            and workspace["alias_b"]["touches"] == 1
        )
    raise ValueError(record["family"])


def aggregate(payload: dict) -> dict:
    result = {}
    for condition in ORDER:
        records = payload["conditions"][condition]["records"]
        families = {}
        for family in FAMILY_ORDER:
            rows = [record for record in records if record["family"] == family]
            families[family] = {
                "n": len(rows),
                "successes": sum(record["success"] for record in rows),
                "mechanism_successes": (
                    sum(mechanism_success(record) for record in rows)
                    if family in {"state_mutation", "reference_identity"}
                    else None
                ),
            }
        result[condition] = {
            "n": len(records),
            "successes": sum(record["success"] for record in records),
            "mean_calls": sum(record["model_calls"] for record in records) / len(records),
            "mean_tokens": sum(record["total_tokens"] for record in records) / len(records),
            "mean_latency_s": sum(record["latency_s"] for record in records) / len(records),
            "failures": dict(
                Counter(
                    record["failure_class"]
                    for record in records
                    if not record["success"]
                )
            ),
            "families": families,
        }
    return result


def style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#FAFAFA",
            "axes.edgecolor": "#CBD5E1",
            "axes.titleweight": "bold",
            "axes.titlesize": 15,
            "font.size": 11,
            "savefig.bbox": "tight",
            "savefig.dpi": 180,
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMAGES / name, facecolor="white")
    plt.close(fig)


def headline(summary: dict) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    labels = [
        "JSON tools",
        "Typed live\nNOOA",
        "NOOA,\nno validation",
        "NOOA,\nserialized copies",
    ]
    successes = [summary[key]["successes"] for key in ORDER]
    totals = [summary[key]["n"] for key in ORDER]
    rates = [100 * s / n for s, n in zip(successes, totals, strict=True)]
    intervals = [wilson(s, n) for s, n in zip(successes, totals, strict=True)]
    yerr = np.array(
        [
            [rate / 100 - low for rate, (low, _) in zip(rates, intervals, strict=True)],
            [high - rate / 100 for rate, (_, high) in zip(rates, intervals, strict=True)],
        ]
    ) * 100
    bars = ax.bar(
        labels,
        rates,
        color=[COLORS[key] for key in ORDER],
        yerr=yerr,
        capsize=5,
        width=0.68,
    )
    ax.set_ylim(0, 100)
    ax.set_ylabel("Executable success (%)")
    ax.set_title("Typed live NOOA did not beat the matched JSON-tool control")
    ax.grid(axis="y", alpha=0.22)
    ax.set_axisbelow(True)
    ax.bar_label(
        bars,
        labels=[
            f"{s}/{n}\n({rate:.1f}%)"
            for s, n, rate in zip(successes, totals, rates, strict=True)
        ],
        padding=5,
        fontsize=10,
    )
    ax.text(
        0.01,
        -0.18,
        "Bars: pooled fresh runs. Whiskers: 95% Wilson intervals. Strict checks include side effects and typed return values.",
        transform=ax.transAxes,
        fontsize=9,
        color="#475569",
    )
    save(fig, "headline_success.png")


def capability_matrix(summary: dict) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    x = np.arange(len(FAMILY_ORDER))
    width = 0.19
    for index, condition in enumerate(ORDER):
        values = [
            100
            * summary[condition]["families"][family]["successes"]
            / summary[condition]["families"][family]["n"]
            for family in FAMILY_ORDER
        ]
        ax.bar(
            x + (index - 1.5) * width,
            values,
            width,
            label=SOURCES[condition]["label"],
            color=COLORS[condition],
        )
    ax.set_xticks(x, [FAMILY_LABELS[family] for family in FAMILY_ORDER])
    ax.set_ylim(0, 108)
    ax.set_ylabel("Executable success (%)")
    ax.set_title("The aggregate result hides a sharp capability split")
    ax.grid(axis="y", alpha=0.22)
    ax.set_axisbelow(True)
    ax.legend(ncol=2, frameon=False, loc="upper center")
    save(fig, "capability_success.png")


def object_mechanisms(payload: dict) -> None:
    conditions = ["json", "nooa", "nooa_serialized"]
    families = ["state_mutation", "reference_identity"]
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    x = np.arange(len(families))
    width = 0.23
    for index, condition in enumerate(conditions):
        records = payload["conditions"][condition]["records"]
        rates = []
        labels = []
        for family in families:
            rows = [record for record in records if record["family"] == family]
            successes = sum(mechanism_success(record) for record in rows)
            rates.append(100 * successes / len(rows))
            labels.append(f"{successes}/{len(rows)}")
        bars = ax.bar(
            x + (index - 1) * width,
            rates,
            width,
            color=COLORS[condition],
            label=SOURCES[condition]["label"],
        )
        ax.bar_label(bars, labels=labels, padding=4, fontsize=9)
    ax.set_xticks(x, ["Required state effect", "Required alias effect"])
    ax.set_ylim(0, 112)
    ax.set_ylabel("Mechanism check success (%)")
    ax.set_title("Serialized copies eliminate the targeted live-object effects")
    ax.grid(axis="y", alpha=0.22)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper center", ncol=3)
    save(fig, "live_object_mechanisms.png")


def validation_effect(summary: dict) -> None:
    conditions = ["nooa", "nooa_no_validation"]
    values = []
    labels = []
    for condition in conditions:
        row = summary[condition]["families"]["typed_nested_output"]
        values.append(100 * row["successes"] / row["n"])
        labels.append(f'{row["successes"]}/{row["n"]}')
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars = ax.bar(
        [SOURCES[condition]["label"] for condition in conditions],
        values,
        color=[COLORS[condition] for condition in conditions],
        width=0.58,
    )
    ax.bar_label(bars, labels=labels, padding=6, fontsize=11)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Typed nested-output success (%)")
    ax.set_title("Removing the return-type contract collapses correctness")
    ax.grid(axis="y", alpha=0.22)
    ax.set_axisbelow(True)
    save(fig, "validation_ablation.png")


def efficiency(summary: dict) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 5.6))
    for condition in ORDER:
        row = summary[condition]
        x = row["mean_tokens"]
        y = 100 * row["successes"] / row["n"]
        size = 160 * row["mean_calls"]
        ax.scatter(
            x,
            y,
            s=size,
            color=COLORS[condition],
            alpha=0.88,
            edgecolor="white",
            linewidth=1.5,
        )
        ax.annotate(
            SOURCES[condition]["label"],
            (x, y),
            xytext=(7, 7),
            textcoords="offset points",
            fontsize=9,
        )
    ax.set_xlabel("Mean tokens per trajectory")
    ax.set_ylabel("Executable success (%)")
    ax.set_title("Code-action conditions used more tokens without higher success")
    ax.grid(alpha=0.22)
    ax.set_axisbelow(True)
    ax.text(
        0.01,
        -0.18,
        "Bubble area scales with mean model calls per trajectory.",
        transform=ax.transAxes,
        fontsize=9,
        color="#475569",
    )
    save(fig, "efficiency_tradeoff.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    payload = refresh_data() if args.refresh else json.loads(DATA.read_text())
    summary = aggregate(payload)
    payload["aggregate"] = summary
    DATA.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    style()
    headline(summary)
    capability_matrix(summary)
    object_mechanisms(payload)
    validation_effect(summary)
    efficiency(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
