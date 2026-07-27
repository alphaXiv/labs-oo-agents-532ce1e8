# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "altair>=5.5.0",
#   "marimo>=0.14.17",
#   "pandas>=2.2.3",
# ]
# ///

import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt
    import marimo as mo
    import pandas as pd

    return alt, mo, pd


@app.cell
def _(mo):
    mo.md(r"""
    # Live objects, typed contracts, and JSON tools

    **Verdict: partially reproduced.** With one public Qwen model and matched
    tasks, typed live NOOA reached **25/60 (41.7%)** executable successes,
    while a minimal JSON-tool loop reached **48/60 (80.0%)**. Two mechanism
    tests did align with the proposed design: runtime validation prevented
    malformed returns, and live references preserved state effects that
    disappeared when objects were serialized into copies.

    This notebook contains the already-produced evidence; opening it does not
    rerun the GPU experiments.
    """)
    return


@app.cell
def _(pd):
    headline = pd.DataFrame(
        [
            {"condition": "JSON tools", "successes": 48, "n": 60, "tokens": 4475, "latency": 7.4},
            {"condition": "Typed live NOOA", "successes": 25, "n": 60, "tokens": 8720, "latency": 37.0},
            {"condition": "NOOA, no validation", "successes": 0, "n": 30, "tokens": 6534, "latency": 31.1},
            {"condition": "NOOA, serialized copies", "successes": 19, "n": 45, "tokens": 10047, "latency": 47.2},
        ]
    )
    headline["success_rate"] = 100 * headline["successes"] / headline["n"]
    headline["label"] = (
        headline["successes"].astype(str)
        + "/"
        + headline["n"].astype(str)
        + " ("
        + headline["success_rate"].round(1).astype(str)
        + "%)"
    )
    return (headline,)


@app.cell
def _(alt, headline, mo):
    colors = ["#64748B", "#76B900", "#F59E0B", "#E45756"]
    headline_chart = (
        alt.Chart(headline)
        .mark_bar()
        .encode(
            x=alt.X("condition:N", sort=None, title=None),
            y=alt.Y("success_rate:Q", title="Executable success (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("condition:N", scale=alt.Scale(range=colors), legend=None),
            tooltip=["condition", "successes", "n", alt.Tooltip("success_rate:Q", format=".1f")],
        )
        .properties(width=650, height=340, title="Strict end-to-end success")
    )
    labels = headline_chart.mark_text(dy=-10, color="#111827").encode(text="label:N")
    mo.ui.altair_chart(headline_chart + labels)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Reading the headline

    Every task had an executable postcheck. A trajectory counted only when
    both the final nested return value and the underlying workspace were
    correct. JSON repeated at 80% across two disjoint six-seed blocks; live
    NOOA ranged from 33% to 53% across three blocks.

    The paper's 4,309/4,400 (97.9%) validation result is not numerically
    comparable: it spans ten models and a different test suite. Here the goal
    is causal—hold the model and tasks fixed and swap only the interface.
    """)
    return


@app.cell
def _(pd):
    capability = pd.DataFrame(
        [
            ("JSON tools", "State mutation", 12, 12),
            ("JSON tools", "Reference identity", 12, 12),
            ("JSON tools", "Typed nested output", 0, 12),
            ("JSON tools", "Error recovery", 12, 12),
            ("JSON tools", "Multi-step tools", 12, 12),
            ("Typed live NOOA", "State mutation", 5, 12),
            ("Typed live NOOA", "Reference identity", 1, 12),
            ("Typed live NOOA", "Typed nested output", 12, 12),
            ("Typed live NOOA", "Error recovery", 7, 12),
            ("Typed live NOOA", "Multi-step tools", 0, 12),
            ("NOOA, no validation", "State mutation", 0, 6),
            ("NOOA, no validation", "Reference identity", 0, 6),
            ("NOOA, no validation", "Typed nested output", 0, 6),
            ("NOOA, no validation", "Error recovery", 0, 6),
            ("NOOA, no validation", "Multi-step tools", 0, 6),
            ("NOOA, serialized copies", "State mutation", 0, 9),
            ("NOOA, serialized copies", "Reference identity", 0, 9),
            ("NOOA, serialized copies", "Typed nested output", 9, 9),
            ("NOOA, serialized copies", "Error recovery", 9, 9),
            ("NOOA, serialized copies", "Multi-step tools", 1, 9),
        ],
        columns=["condition", "capability", "successes", "n"],
    )
    capability["rate"] = 100 * capability["successes"] / capability["n"]
    return (capability,)


@app.cell
def _(alt, capability, mo):
    capability_chart = (
        alt.Chart(capability)
        .mark_bar()
        .encode(
            x=alt.X(
                "capability:N",
                title=None,
                sort=[
                    "State mutation",
                    "Reference identity",
                    "Typed nested output",
                    "Error recovery",
                    "Multi-step tools",
                ],
            ),
            xOffset="condition:N",
            y=alt.Y("rate:Q", title="Executable success (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color(
                "condition:N",
                scale=alt.Scale(range=["#64748B", "#76B900", "#F59E0B", "#E45756"]),
                title=None,
            ),
            tooltip=["condition", "capability", "successes", "n"],
        )
        .properties(width=670, height=330, title="The interface trade-off depends on capability")
    )
    mo.ui.altair_chart(capability_chart)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Mechanism checks

    Strict answers obscure a useful distinction. Live NOOA performed the
    required state mutation in **12/12** trials and the required shared-alias
    effect in **11/12**, although it often returned the wrong checksum.
    Replacing references with serialized copies reduced both mechanism checks
    to **0/9**. The JSON harness also achieved both effects in **12/12**, using
    server-side state and serialized alias names.

    Runtime return validation was similarly causal: typed NOOA repaired the
    nested output in **12/12** trials, whereas the otherwise matched `Any`
    return annotation succeeded in **0/6**. Across every no-validation task,
    strict success was **0/30**.
    """)
    return


@app.cell
def _(alt, headline, mo):
    efficiency_chart = (
        alt.Chart(headline)
        .mark_circle(opacity=0.88, stroke="white", strokeWidth=2, size=500)
        .encode(
            x=alt.X("tokens:Q", title="Mean tokens per trajectory"),
            y=alt.Y("success_rate:Q", title="Executable success (%)"),
            color=alt.Color(
                "condition:N",
                scale=alt.Scale(range=["#64748B", "#76B900", "#F59E0B", "#E45756"]),
                legend=None,
            ),
            tooltip=["condition", "tokens", "latency", alt.Tooltip("success_rate:Q", format=".1f")],
        )
        .properties(width=650, height=330, title="Efficiency did not improve")
    )
    text = efficiency_chart.mark_text(dx=8, dy=-8, align="left", color="#111827").encode(
        text="condition:N"
    )
    mo.ui.altair_chart(efficiency_chart + text)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## What the experiment supports

    | Claim | Evidence | Assessment |
    |---|---:|---|
    | Typed live interface beats JSON tools | 25/60 vs 48/60 | Not aligned here |
    | Runtime validation improves correctness | 12/12 vs 0/6 nested outputs | Aligned |
    | Pass-by-reference preserves effects | 23/24 vs 0/18 mechanism checks | Aligned |
    | Code action is more efficient | 8,720 vs 4,475 mean tokens | Not aligned here |

    The bounded suite omits SWE-bench, Terminal-Bench, ARC-AGI-3, and the
    paper's ten-model matrix. Its JSON comparator is deliberately minimal.
    Checksums also exposed a model-specific failure mode: generated code
    sometimes tried to derive a checksum that the prompt had explicitly
    supplied.

    **Compute provenance:** OpenResearch Kubernetes backend; NVIDIA RTX PRO
    6000 Blackwell GPUs; peak 16 GPUs concurrently; 1.15 hours actual elapsed
    wall time. The public
    [report](https://github.com/alphaXiv/labs-oo-agents-532ce1e8/blob/main/reports/interface-reproduction/report.md)
    links the complete compact records and experiment branches.
    """)
    return


if __name__ == "__main__":
    app.run()
