"""Render the report figures from the frozen terminal-summary dataset."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).parent
OUT = ROOT / "images"
DATA = json.loads((ROOT / "results.json").read_text())
CONDS = DATA["conditions"]

COLORS = {
    "json": "#4C78A8",
    "nooa": "#59A14F",
    "nooa_serialized": "#F28E2B",
    "nooa_no_validation": "#E15759",
}

plt.rcParams.update(
    {
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)
OUT.mkdir(parents=True, exist_ok=True)


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = successes / n
    denominator = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return centre - half, centre + half


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=180, bbox_inches="tight")
    plt.close()


# 1. Headline aggregate executable success.
keys = ["json", "nooa", "nooa_serialized", "nooa_no_validation"]
labels = [CONDS[k]["label"] for k in keys]
rates = [CONDS[k]["successes"] / CONDS[k]["n"] for k in keys]
intervals = [wilson(CONDS[k]["successes"], CONDS[k]["n"]) for k in keys]
lower = [r - lo for r, (lo, _) in zip(rates, intervals, strict=True)]
upper = [hi - r for r, (_, hi) in zip(rates, intervals, strict=True)]
fig, ax = plt.subplots(figsize=(8.4, 4.8))
bars = ax.bar(
    labels,
    rates,
    color=[COLORS[k] for k in keys],
    yerr=np.array([lower, upper]),
    capsize=5,
)
ax.set_ylim(0, 1.02)
ax.set_ylabel("Executable success rate")
ax.set_title("A strong JSON control beat NOOA overall; validation was essential")
ax.grid(axis="y", alpha=0.25)
for bar, key, rate in zip(bars, keys, rates, strict=True):
    item = CONDS[key]
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        rate + 0.055,
        f"{item['successes']}/{item['n']}\n{rate:.0%}",
        ha="center",
        va="bottom",
        fontsize=10,
    )
save("01_headline_success.png")


# 2. Capability-specific outcome matrix.
families = [
    ("state_mutation", "State mutation"),
    ("reference_identity", "Reference identity"),
    ("typed_nested_output", "Typed nested output"),
    ("error_recovery", "Error recovery"),
    ("multi_step_tools", "Multi-step tools"),
]
matrix = np.array(
    [
        [
            CONDS[key]["families"][family][0]
            / CONDS[key]["families"][family][1]
            for family, _ in families
        ]
        for key in keys
    ]
)
fig, ax = plt.subplots(figsize=(10.5, 5.0))
image = ax.imshow(matrix, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
ax.set_xticks(
    range(len(families)),
    [label for _, label in families],
    rotation=15,
    ha="right",
)
ax.set_yticks(range(len(keys)), labels)
for row, key in enumerate(keys):
    for col, (family, _) in enumerate(families):
        successes, n = CONDS[key]["families"][family]
        ax.text(
            col,
            row,
            f"{successes}/{n}\n{successes / n:.0%}",
            ha="center",
            va="center",
            color="black",
            fontsize=10,
        )
fig.colorbar(image, ax=ax, label="Executable success rate", fraction=0.03)
ax.set_title("The interface effect depended sharply on the capability")
save("02_capability_matrix.png")


# 3. Seed-set robustness.
fig, ax = plt.subplots(figsize=(8.4, 4.8))
for offset, key in enumerate(["json", "nooa", "nooa_serialized", "nooa_no_validation"]):
    reps = DATA["replications"][key]
    xs = np.arange(len(reps)) + offset * 0.2
    ys = [item["successes"] / item["n"] for item in reps]
    ax.plot(
        xs,
        ys,
        marker="o",
        linewidth=2,
        markersize=7,
        color=COLORS[key],
        label=CONDS[key]["label"],
    )
    for x, y, item in zip(xs, ys, reps, strict=True):
        ax.annotate(
            f"{item['successes']}/{item['n']}",
            (x, y),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=9,
        )
ax.set_xticks([0.3, 1.3, 2.3], ["Seed batch A", "Seed batch B", "Seed batch C"])
ax.set_xlim(-0.25, 2.65)
ax.set_ylim(-0.04, 1.04)
ax.set_ylabel("Executable success rate")
ax.set_title("The headline ordering persisted across repeated seed batches")
ax.grid(axis="y", alpha=0.25)
ax.legend(frameon=False, ncol=2, loc="upper right")
save("03_seed_robustness.png")


# 4. Efficiency trade-off.
fig, ax = plt.subplots(figsize=(8.4, 5.0))
for key in keys:
    item = CONDS[key]
    calls = item["model_calls"] / item["n"]
    tokens = item["tokens"] / item["n"]
    latency = item["trajectory_wall_s"] / item["n"]
    ax.scatter(
        calls,
        tokens,
        s=55 + latency * 7,
        color=COLORS[key],
        edgecolor="white",
        linewidth=1.2,
        label=f"{item['label']} ({latency:.1f}s/task)",
    )
    ax.annotate(item["label"], (calls, tokens), xytext=(7, 5), textcoords="offset points")
ax.set_xlabel("Model calls per task (lower is better)")
ax.set_ylabel("Tokens per task (lower is better)")
ax.set_title("NOOA used fewer calls, but more tokens and wall time")
ax.grid(alpha=0.25)
ax.legend(frameon=False, fontsize=9, loc="upper right")
save("04_efficiency.png")


# 5. Diagnostic failure classes.
failure_order = [
    "contract_invalid",
    "wrong_checksum",
    "wrong_answer",
    "state_not_mutated",
    "harness_exception",
    "identity_or_alias_effect_lost",
]
failure_labels = {
    "contract_invalid": "Invalid contract",
    "wrong_checksum": "Wrong checksum",
    "wrong_answer": "Wrong answer",
    "state_not_mutated": "State not mutated",
    "harness_exception": "Harness exception",
    "identity_or_alias_effect_lost": "Identity lost",
}
failure_colors = ["#E15759", "#B07AA1", "#FF9DA7", "#F28E2B", "#9C755F", "#BAB0AC"]
fig, ax = plt.subplots(figsize=(9.2, 4.8))
bottom = np.zeros(len(keys))
for failure, color in zip(failure_order, failure_colors, strict=True):
    values = np.array([CONDS[key]["failures"].get(failure, 0) for key in keys])
    ax.bar(labels, values, bottom=bottom, label=failure_labels[failure], color=color)
    bottom += values
ax.set_ylabel("Failed trajectories")
ax.set_title("Removing validation converted nearly every trajectory into an invalid contract")
ax.legend(frameon=False, ncol=3, fontsize=9, loc="upper left")
ax.grid(axis="y", alpha=0.2)
save("05_failure_classes.png")
