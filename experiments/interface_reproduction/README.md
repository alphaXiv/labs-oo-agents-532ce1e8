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
dependent employee-directory/payroll calculation. The first matched round ran
all five families at six fixed sampling seeds; disjoint seed blocks then tested
robustness. The four conditions are:

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

Fresh Kubernetes runs created after 2026-07-27T00:54:41.419Z produced 195
fully summarized trajectories. Strict executable success was 48/60 (80.0%)
for JSON tools, 25/60 (41.7%) for typed live NOOA, 0/30 without return
validation, and 19/45 (42.2%) with serialized copies. Thus this Qwen setup did
not show an aggregate NOOA advantage.

The mechanism checks were more favorable. Typed NOOA repaired nested output in
12/12 trials versus 0/6 without validation. Live NOOA preserved 23/24 required
state or alias effects, while serialized copies preserved 0/18. JSON
server-side tools preserved 24/24 corresponding effects. See the
[illustrated report](../../reports/interface-reproduction/report.md) and
[compact records](../../reports/interface-reproduction/data/results.json).

Compute used OpenResearch Kubernetes, NVIDIA RTX PRO 6000 Blackwell GPUs, a
peak of 16 GPUs concurrently, and 1.15 hours actual elapsed wall time.
