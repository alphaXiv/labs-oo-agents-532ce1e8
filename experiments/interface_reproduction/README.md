# Typed live objects versus serialized JSON tools

## Research question

With one local Qwen instruction model, task prompts, sampling, turn limits, and
executable checks held fixed, does NOOA's typed live-object CodeAct interface
improve reliability or efficiency over a minimal JSON-schema tool loop? Do
return-type validation and pass-by-reference account for capability-specific
gains?

## Experiment design

The suite has five synthetic but executable capability families derived from
the paper's targeted tests: live state mutation, pass-by-reference alias
identity, nested typed output, recovery from a transient exception, and a
dependent employee-directory/payroll calculation. Each condition runs all five
families at six fixed sampling seeds. The four conditions are:

1. `json`: conventional JSON-schema tool calls with serialized observations.
2. `nooa`: released NOOA CodeAct with typed live Python arguments and returns.
3. `nooa_no_validation`: the same NOOA tools and live objects, but `solve`
   returns `Any`, removing the runtime return contract.
4. `nooa_serialized`: NOOA CodeAct receives a JSON snapshot and copy-returning
   helpers instead of the live workspace.

The JSON comparator is intentionally small and transparent. It keeps
environment state in the harness, exposes ordinary function schemas, serializes
every observation, and validates the same final Pydantic contract. It is not a
claim to reproduce OpenCode, PI, SWE-bench, or Terminal-Bench.

## Key metrics

Executable success is primary. Secondary metrics are model calls, input/output
tokens, wall latency, tool or validation retries, exceptions, and
trace-classified failure modes. Identity and state tests inspect the underlying
Python objects after the model finishes; returning the expected text without
the side effect does not pass.

## How to run

The OpenResearch project uses one fixed command on every experiment node:

```bash
uv sync --frozen --extra repro && uv run --extra repro python experiments/interface_reproduction/run.py
```

The committed Kubernetes manifest requests four NVIDIA GPUs and executes the
injected OpenResearch script. The Python entrypoint starts one local vLLM server
for `Qwen/Qwen3-30B-A3B-Instruct-2507` with tensor parallelism across the four
GPUs, runs the configured condition, and prints all evidence plus a compact
`REPRO_RESULT_JSON` record to the terminal log.

## Results summary

Only complete Kubernetes runs created after 2026-07-27T00:54:41.419Z are
counted. Aggregating independent seed batches, the JSON loop passed 48/60
(80.0%), live NOOA passed 25/60 (41.7%), serialized-copy NOOA passed 19/45
(42.2%), and NOOA without runtime return validation passed 0/30. Live NOOA was
perfect on nested typed output (12/12), while JSON was 0/12. Over nine matched
seeds, live objects passed state mutation 3/9 versus 0/9 for serialized copies;
reference identity was 0/9 in both. The detailed synthesis, figures, limitations,
and terminal evidence IDs are in
[`reports/interface-reproduction/report.md`](../../reports/interface-reproduction/report.md)
and [`results.json`](../../reports/interface-reproduction/results.json).

All formal evidence used OpenResearch Kubernetes, four NVIDIA RTX PRO 6000
Blackwell GPUs per job, and 16 GPUs peak concurrently. The recovery evidence
window lasted 1.15 elapsed hours.
