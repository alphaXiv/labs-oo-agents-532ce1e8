# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "marimo>=0.16.0",
#   "matplotlib>=3.9",
#   "numpy>=2.0",
# ]
# ///

import marimo

__generated_with = "0.16.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.md(
        r"""
        # Live Python objects versus JSON tools

        Most agents call tools through serialized records. NOOA instead lets a model write
        Python that acts on typed, live objects. This notebook embeds the completed
        Kubernetes evidence for a bounded reproduction of that interface claim—no
        expensive rerun or repository-relative data file is required.

        **Verdict: partially reproduced.** Runtime return validation was essential and
        live references helped state mutation, but the aggregate interface advantage did
        not appear: JSON tools passed **48/60 (80.0%)** tasks, versus **25/60 (41.7%)**
        for live NOOA.
        """
    )
    return (mo,)


@app.cell
def _():
    results = {
        "JSON tools": {
            "successes": 48,
            "n": 60,
            "calls": 240,
            "tokens": 268495,
            "seconds": 445.292,
            "families": [12, 12, 0, 12, 12],
            "family_n": [12, 12, 12, 12, 12],
        },
        "NOOA live": {
            "successes": 25,
            "n": 60,
            "calls": 143,
            "tokens": 523223,
            "seconds": 2220.827,
            "families": [5, 1, 12, 7, 0],
            "family_n": [12, 12, 12, 12, 12],
        },
        "NOOA copies": {
            "successes": 19,
            "n": 45,
            "calls": 111,
            "tokens": 452106,
            "seconds": 2122.246,
            "families": [0, 0, 9, 9, 1],
            "family_n": [9, 9, 9, 9, 9],
        },
        "NOOA no validation": {
            "successes": 0,
            "n": 30,
            "calls": 60,
            "tokens": 196008,
            "seconds": 932.715,
            "families": [0, 0, 0, 0, 0],
            "family_n": [6, 6, 6, 6, 6],
        },
    }
    colors = ["#4C78A8", "#59A14F", "#F28E2B", "#E15759"]
    families = [
        "State mutation",
        "Reference identity",
        "Typed nested output",
        "Error recovery",
        "Multi-step tools",
    ]
    return colors, families, results


@app.cell
def _(colors, mo, results):
    import matplotlib.pyplot as _plt

    _names1 = list(results)
    _rates1 = [
        results[_condition_name]["successes"] / results[_condition_name]["n"]
        for _condition_name in _names1
    ]
    _fig1, _ax1 = _plt.subplots(figsize=(9, 4.5))
    _bars1 = _ax1.bar(_names1, _rates1, color=colors)
    _ax1.set_ylim(0, 1)
    _ax1.set_ylabel("Executable success rate")
    _ax1.set_title("A strong JSON control beat NOOA overall")
    _ax1.grid(axis="y", alpha=0.25)
    for _bar1, _name1, _rate1 in zip(_bars1, _names1, _rates1, strict=True):
        _item1 = results[_name1]
        _ax1.text(
            _bar1.get_x() + _bar1.get_width() / 2,
            _rate1 + 0.025,
            f"{_item1['successes']}/{_item1['n']} ({_rate1:.0%})",
            ha="center",
        )
    mo.mpl.interactive(_fig1)
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        The bars count only terminal runs with a nonempty `REPRO_RESULT_JSON`.
        Whisker-free notebook plots emphasize the exact counts; the report adds Wilson
        intervals and trace-classified diagnostics.

        ## Matched design

        One locally served `Qwen/Qwen3-30B-A3B-Instruct-2507` model saw the same task
        intent and data at temperature 0.2, top-p 0.9, six turns, and 1,200 output tokens
        per turn. Hidden checks inspected state and identity rather than trusting the
        response text. The five task families isolate the mechanisms named by the paper.

        The JSON control retained environment state behind ordinary JSON-schema tools.
        Live NOOA exposed the real workspace to CodeAct. One ablation changed the return
        type to `Any`; another exposed serialized snapshots and copy-returning helpers.
        """
    )
    return


@app.cell
def _(colors, families, mo, results):
    import matplotlib.pyplot as _plt
    import numpy as _np

    _names2 = list(results)
    _matrix2 = _np.array(
        [
            [
                success / n
                for success, n in zip(
                    results[name]["families"],
                    results[name]["family_n"],
                    strict=True,
                )
            ]
            for name in _names2
        ]
    )
    _fig2, _ax2 = _plt.subplots(figsize=(10, 4.3))
    _image2 = _ax2.imshow(_matrix2, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    _ax2.set_xticks(range(len(families)), families)
    _ax2.set_yticks(range(len(_names2)), _names2)
    for _row2, _name2 in enumerate(_names2):
        for _col2 in range(len(families)):
            _success2 = results[_name2]["families"][_col2]
            _n2 = results[_name2]["family_n"][_col2]
            _ax2.text(
                _col2,
                _row2,
                f"{_success2}/{_n2}",
                ha="center",
                va="center",
            )
    _fig2.colorbar(_image2, ax=_ax2, label="Success rate", fraction=0.03)
    _ax2.set_title("Capability-specific executable success")
    mo.mpl.interactive(_fig2)
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        The matrix explains the partial verdict. NOOA's typed return was perfect on nested
        output, where JSON failed every contract. JSON was otherwise much stronger.
        Replacing live references with copies reduced state mutation from **3/9 to 0/9**
        on matched seeds, but identity remained 0/9 in both conditions.

        ## Validation mechanism

        Two complete unvalidated batches produced **0/30** successes: 29 invalid return
        contracts and one harness exception. Validated live NOOA produced **25/60**.
        This is the clearest aligned mechanism result, though counts differ because the
        ablation was stopped once two independent batches repeated the same complete
        collapse.
        """
    )
    return


@app.cell
def _(colors, mo, results):
    condition = mo.ui.dropdown(
        options=list(results),
        value="NOOA live",
        label="Inspect efficiency:",
    )
    mo.vstack([condition])
    return (condition,)


@app.cell
def _(condition, mo, results):
    _selected = results[condition.value]
    mo.md(
        f"""
        **{condition.value}**

        - Success: **{_selected["successes"]}/{_selected["n"]}**
        - Model calls per task: **{_selected["calls"] / _selected["n"]:.2f}**
        - Tokens per task: **{_selected["tokens"] / _selected["n"]:,.0f}**
        - Summed trajectory wall time per task: **{_selected["seconds"] / _selected["n"]:.1f} s**

        Live NOOA used fewer calls than JSON (2.38 vs 4.00), but about twice the tokens
        and five times the trajectory wall time. Fewer model round trips did not mean a
        cheaper run for this model.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## What this does—and does not—show

        The released framework mechanisms are real: validation prevented malformed
        contracts, and live references enabled some genuine side effects. This small
        Qwen model nevertheless handled conventional JSON tools much more reliably on
        four of five families. The synthetic suite is designed for causal checks; it is
        not SWE-bench, Terminal-Bench, ARC, or a reproduction of the paper's external
        baselines.

        All formal runs used OpenResearch **Kubernetes**, four **NVIDIA RTX PRO 6000
        Blackwell** GPUs per job, and **16 GPUs peak concurrently**. The fresh evidence
        window lasted **1.15 elapsed hours** (2026-07-27 00:55:19–02:04:28 UTC).

        Read the [paper](https://arxiv.org/abs/2607.20709), the
        [full report](https://github.com/alphaXiv/labs-oo-agents-532ce1e8/blob/main/reports/interface-reproduction/report.md),
        or the [frozen result data](https://github.com/alphaXiv/labs-oo-agents-532ce1e8/blob/main/reports/interface-reproduction/results.json).
        """
    )
    return


if __name__ == "__main__":
    app.run()
