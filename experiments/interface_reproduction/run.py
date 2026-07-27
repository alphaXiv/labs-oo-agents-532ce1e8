"""Matched causal reproduction of NOOA interface capabilities.

All formal evidence is emitted to stdout because OpenResearch local mode uses
terminal logs as its evidence channel.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from nooa import Agent, CodeActStrategy, strategy
from nooa.config import CodeActConfig
from nooa.unifiedllm import CompletionClient, Tool

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text())
API_BASE = "http://127.0.0.1:8000/v1"
COMMON_INTENT = (
    "Complete the capability task using the available interface. Be precise, "
    "recover from tool errors, preserve required side effects, and finish by "
    "submitting the requested structured result. Do not merely describe actions."
)


class AnswerDetails(BaseModel):
    steps: list[str]
    checksum: int


class CapabilityAnswer(BaseModel):
    primary: str | int
    details: AnswerDetails


class CapabilityResult(BaseModel):
    status: Literal["complete"]
    answer: CapabilityAnswer
    evidence: list[str]


class TaskCase(BaseModel):
    family: str
    prompt: str
    expected_primary: str | int
    expected_checksum: int


@dataclass
class AliasNode:
    label: str
    touches: int = 0


@dataclass
class LiveWorkspace:
    counter: int = 0
    journal: list[str] = field(default_factory=list)
    alias_a: AliasNode = field(default_factory=lambda: AliasNode("unmodified"))
    alias_b: AliasNode | None = None
    unstable_attempts: int = 0

    def __post_init__(self) -> None:
        if self.alias_b is None:
            self.alias_b = self.alias_a

    def snapshot(self) -> dict[str, Any]:
        assert self.alias_b is not None
        return {
            "counter": self.counter,
            "journal": list(self.journal),
            "alias_a": {"label": self.alias_a.label, "touches": self.alias_a.touches},
            "alias_b": {"label": self.alias_b.label, "touches": self.alias_b.touches},
            "aliases_share_identity": self.alias_a is self.alias_b,
            "unstable_attempts": self.unstable_attempts,
        }


EMPLOYEES = {
    "Ada Lovelace": {"employee_id": "E-1843", "department": "Research"},
    "Grace Hopper": {"employee_id": "E-2718", "department": "Systems"},
}
PAYROLL = {
    "E-1843": {"base_salary": 182_000, "bonus": 18_000, "total": 200_000},
    "E-2718": {"base_salary": 168_000, "bonus": 12_000, "total": 180_000},
}


class TrackingCompletionClient(CompletionClient):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    async def acall(self, *args: Any, **kwargs: Any):
        response = await super().acall(*args, **kwargs)
        self.calls += 1
        usage = response.usage or {}
        self.input_tokens += int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
        self.output_tokens += int(
            usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
        )
        return response


CODEACT_CONFIG = CodeActConfig(
    max_iterations=int(CONFIG["max_turns"]),
    max_retries=2,
    max_tokens=int(CONFIG["max_tokens"]),
    temperature=float(CONFIG["temperature"]),
    top_p=float(CONFIG["top_p"]),
)


class LiveCapabilityAgent(Agent):
    """Capability agent with a live Python workspace and deterministic helpers."""

    workspace: LiveWorkspace

    def __init__(self, workspace: LiveWorkspace, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.workspace = workspace

    def increment(self, amount: int, label: str) -> dict[str, Any]:
        """Mutate the live counter and append the exact label to its journal."""
        self.workspace.counter += amount
        self.workspace.journal.append(label)
        return self.workspace.snapshot()

    def relabel_alias(self, alias: Literal["alias_a", "alias_b"], label: str) -> dict[str, Any]:
        """Mutate one live alias. Both aliases may refer to the same Python object."""
        node = getattr(self.workspace, alias)
        assert node is not None
        node.label = label
        node.touches += 1
        return self.workspace.snapshot()

    def inspect_workspace(self) -> dict[str, Any]:
        """Return a bounded snapshot of the current live workspace."""
        return self.workspace.snapshot()

    def unstable_fetch(self, key: str) -> dict[str, Any]:
        """Fetch a value; the first call raises a transient exception and retrying succeeds."""
        self.workspace.unstable_attempts += 1
        if self.workspace.unstable_attempts == 1:
            raise RuntimeError("transient 503: retry the same key")
        return {"key": key, "value": "RECOVERED-73"}

    def lookup_employee(self, name: str) -> dict[str, Any]:
        """Look up an employee by exact name."""
        return dict(EMPLOYEES[name])

    def lookup_payroll(self, employee_id: str) -> dict[str, Any]:
        """Look up payroll by employee ID, not by name."""
        return dict(PAYROLL[employee_id])

    def salary_band(self, total: int) -> str:
        """Map total compensation to the deterministic band."""
        return "A" if total >= 190_000 else "B"

    def malformed_candidate(self, primary: str | int) -> dict[str, Any]:
        """Return a tempting but deliberately malformed draft that must be repaired."""
        return {
            "status": "complete",
            "answer": {
                "primary": primary,
                "details": {"steps": "draft-not-a-list", "checksum": "not-an-int"},
            },
        }

    @strategy(CodeActStrategy(config=CODEACT_CONFIG))
    async def solve(self, task: TaskCase) -> CapabilityResult:
        """Solve the task. Use live methods and return a contract-valid result."""
        ...


class UntypedCapabilityAgent(LiveCapabilityAgent):
    @strategy(CodeActStrategy(config=CODEACT_CONFIG))
    async def solve(self, task: TaskCase) -> Any:
        """Solve the task. Use live methods and return the requested result shape."""
        ...


class SerializedCapabilityAgent(Agent):
    """CodeAct agent restricted to serialized snapshots and copy-returning helpers."""

    _workspace: LiveWorkspace

    def __init__(self, workspace: LiveWorkspace, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._workspace = workspace

    def mutate_copy(
        self, payload_json: str, operation: Literal["increment", "relabel"], value: str
    ) -> str:
        """Apply an operation to a deserialized copy and return a new JSON copy."""
        payload = json.loads(payload_json)
        if operation == "increment":
            amount_text, label = value.split("|", 1)
            payload["counter"] += int(amount_text)
            payload["journal"].append(label)
        else:
            payload["alias_a"]["label"] = value
            payload["alias_a"]["touches"] += 1
        return json.dumps(payload, sort_keys=True)

    def unstable_fetch(self, key: str) -> dict[str, Any]:
        """Fetch a value; the first call raises a transient exception and retrying succeeds."""
        self._workspace.unstable_attempts += 1
        if self._workspace.unstable_attempts == 1:
            raise RuntimeError("transient 503: retry the same key")
        return {"key": key, "value": "RECOVERED-73"}

    def lookup_employee(self, name: str) -> dict[str, Any]:
        """Look up an employee by exact name."""
        return dict(EMPLOYEES[name])

    def lookup_payroll(self, employee_id: str) -> dict[str, Any]:
        """Look up payroll by employee ID, not by name."""
        return dict(PAYROLL[employee_id])

    def salary_band(self, total: int) -> str:
        """Map total compensation to the deterministic band."""
        return "A" if total >= 190_000 else "B"

    def malformed_candidate(self, primary: str | int) -> dict[str, Any]:
        """Return a tempting but deliberately malformed draft that must be repaired."""
        return {
            "status": "complete",
            "answer": {
                "primary": primary,
                "details": {"steps": "draft-not-a-list", "checksum": "not-an-int"},
            },
        }

    @strategy(CodeActStrategy(config=CODEACT_CONFIG))
    async def solve(self, task: TaskCase, payload_json: str) -> CapabilityResult:
        """Solve using only the serialized snapshot and copy-returning helpers."""
        ...


class IncrementArgs(BaseModel):
    amount: int
    label: str


class RelabelArgs(BaseModel):
    alias: Literal["alias_a", "alias_b"]
    label: str


class KeyArgs(BaseModel):
    key: str


class NameArgs(BaseModel):
    name: str


class EmployeeIdArgs(BaseModel):
    employee_id: str


class TotalArgs(BaseModel):
    total: int


class CandidateArgs(BaseModel):
    primary: str | int


class SubmitArgs(CapabilityResult):
    pass


class NoArgs(BaseModel):
    pass


class JsonToolHarness:
    def __init__(self, workspace: LiveWorkspace) -> None:
        self.workspace = workspace
        self.tool_errors = 0
        self.validation_retries = 0
        self.submitted: CapabilityResult | None = None

    def increment(self, amount: int, label: str) -> dict[str, Any]:
        """Increment server state and append a journal label."""
        self.workspace.counter += amount
        self.workspace.journal.append(label)
        return self.workspace.snapshot()

    def relabel_alias(self, alias: str, label: str) -> dict[str, Any]:
        """Relabel a server-side object addressed by a serialized alias name."""
        node = getattr(self.workspace, alias)
        assert node is not None
        node.label = label
        node.touches += 1
        return self.workspace.snapshot()

    def inspect_workspace(self) -> dict[str, Any]:
        """Return a serialized snapshot of server state."""
        return self.workspace.snapshot()

    def unstable_fetch(self, key: str) -> dict[str, Any]:
        """Fetch a value. The first request fails transiently; retrying succeeds."""
        self.workspace.unstable_attempts += 1
        if self.workspace.unstable_attempts == 1:
            raise RuntimeError("transient 503: retry the same key")
        return {"key": key, "value": "RECOVERED-73"}

    def lookup_employee(self, name: str) -> dict[str, Any]:
        """Look up an employee by exact name."""
        return dict(EMPLOYEES[name])

    def lookup_payroll(self, employee_id: str) -> dict[str, Any]:
        """Look up payroll by employee ID, not by name."""
        return dict(PAYROLL[employee_id])

    def salary_band(self, total: int) -> str:
        """Map total compensation to band A or B."""
        return "A" if total >= 190_000 else "B"

    def malformed_candidate(self, primary: str | int) -> dict[str, Any]:
        """Return a deliberately malformed draft that should be repaired."""
        return {
            "status": "complete",
            "answer": {
                "primary": primary,
                "details": {"steps": "draft-not-a-list", "checksum": "not-an-int"},
            },
        }

    def tools(self) -> list[Tool]:
        return [
            Tool("increment", self.increment.__doc__ or "", self.increment, IncrementArgs),
            Tool("relabel_alias", self.relabel_alias.__doc__ or "", self.relabel_alias, RelabelArgs),
            Tool(
                "inspect_workspace",
                self.inspect_workspace.__doc__ or "",
                self.inspect_workspace,
                NoArgs,
            ),
            Tool("unstable_fetch", self.unstable_fetch.__doc__ or "", self.unstable_fetch, KeyArgs),
            Tool(
                "lookup_employee",
                self.lookup_employee.__doc__ or "",
                self.lookup_employee,
                NameArgs,
            ),
            Tool(
                "lookup_payroll",
                self.lookup_payroll.__doc__ or "",
                self.lookup_payroll,
                EmployeeIdArgs,
            ),
            Tool("salary_band", self.salary_band.__doc__ or "", self.salary_band, TotalArgs),
            Tool(
                "malformed_candidate",
                self.malformed_candidate.__doc__ or "",
                self.malformed_candidate,
                CandidateArgs,
            ),
            Tool(
                "submit_result",
                "Submit the final result. The schema is executable and validated.",
                lambda **kwargs: kwargs,
                SubmitArgs,
            ),
        ]

    async def run(
        self, task: TaskCase, client: TrackingCompletionClient
    ) -> CapabilityResult | None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": COMMON_INTENT},
            {"role": "user", "content": task.prompt},
        ]
        tool_map = {tool.name: tool for tool in self.tools()}
        for _ in range(int(CONFIG["max_turns"])):
            response = await client.acall(
                messages,
                tools=list(tool_map.values()),
                max_tokens=int(CONFIG["max_tokens"]),
                temperature=float(CONFIG["temperature"]),
                top_p=float(CONFIG["top_p"]),
            )
            messages.append(response.assistant_message)
            if not response.tool_calls:
                messages.append(
                    {
                        "role": "user",
                        "content": "Use submit_result; plain text does not complete the task.",
                    }
                )
                self.validation_retries += 1
                continue
            for call in response.tool_calls:
                try:
                    raw_args = json.loads(call.arguments or "{}")
                    if call.name == "submit_result":
                        self.submitted = CapabilityResult.model_validate(raw_args)
                        return self.submitted
                    tool = tool_map[call.name]
                    assert tool.parameters_model is not None
                    parsed = tool.parameters_model.model_validate(raw_args)
                    result = tool.callable(**parsed.model_dump())
                    content = json.dumps({"ok": True, "result": result}, default=str)
                except (ValidationError, ValueError, KeyError, RuntimeError, AssertionError) as exc:
                    self.tool_errors += 1
                    if call.name == "submit_result":
                        self.validation_retries += 1
                    content = json.dumps(
                        {
                            "ok": False,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "instruction": "Correct the arguments or retry.",
                        }
                    )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": content,
                    }
                )
        return None


def make_tasks() -> list[TaskCase]:
    return [
        TaskCase(
            family="state_mutation",
            expected_primary=12,
            expected_checksum=1202,
            prompt=(
                f"{COMMON_INTENT} Increment the live counter by 7 with label 'alpha', then by 5 "
                "with label 'beta'. The underlying workspace must end at counter 12 with journal "
                "['alpha','beta']. Return primary=12, details.steps naming both mutations, "
                "details.checksum=1202, and nonempty evidence."
            ),
        ),
        TaskCase(
            family="reference_identity",
            expected_primary="shared-green",
            expected_checksum=771,
            prompt=(
                f"{COMMON_INTENT} Relabel alias_a to 'shared-green'. The executable check requires "
                "alias_b to observe the same label through shared object identity and exactly one "
                "touch. Return primary='shared-green', checksum=771, steps, and evidence."
            ),
        ),
        TaskCase(
            family="typed_nested_output",
            expected_primary="typed-ok",
            expected_checksum=31415,
            prompt=(
                f"{COMMON_INTENT} First call malformed_candidate('typed-ok'), then submit a repaired "
                "result with primary='typed-ok', details.steps as a list of strings, "
                "details.checksum=31415, status='complete', and nonempty evidence."
            ),
        ),
        TaskCase(
            family="error_recovery",
            expected_primary="RECOVERED-73",
            expected_checksum=5032,
            prompt=(
                f"{COMMON_INTENT} Call unstable_fetch with key 'weather'. Its first call fails "
                "transiently; recover by retrying the same operation. Return primary='RECOVERED-73', "
                "checksum=5032, steps, and evidence. Two fetch attempts are required."
            ),
        ),
        TaskCase(
            family="multi_step_tools",
            expected_primary="E-1843:A",
            expected_checksum=200043,
            prompt=(
                f"{COMMON_INTENT} Look up Ada Lovelace, use the returned employee_id to query "
                "payroll, then derive the salary band from total compensation. Return "
                "primary='E-1843:A', checksum=200043, ordered steps, and evidence."
            ),
        ),
    ]


def classify_result(
    task: TaskCase,
    raw_result: Any,
    workspace: LiveWorkspace,
    exception: str | None,
) -> tuple[bool, str]:
    if exception:
        return False, "harness_exception"
    try:
        result = CapabilityResult.model_validate(raw_result)
    except ValidationError:
        return False, "contract_invalid"
    if result.answer.primary != task.expected_primary:
        return False, "wrong_answer"
    if result.answer.details.checksum != task.expected_checksum:
        return False, "wrong_checksum"
    if not result.answer.details.steps or not result.evidence:
        return False, "missing_evidence"
    if task.family == "state_mutation":
        if workspace.counter != 12 or workspace.journal != ["alpha", "beta"]:
            return False, "state_not_mutated"
    elif task.family == "reference_identity":
        if (
            workspace.alias_a is not workspace.alias_b
            or workspace.alias_a.label != "shared-green"
            or workspace.alias_b is None
            or workspace.alias_b.label != "shared-green"
            or workspace.alias_a.touches != 1
        ):
            return False, "identity_or_alias_effect_lost"
    elif task.family == "error_recovery" and workspace.unstable_attempts < 2:
        return False, "error_not_retried"
    return True, "success"


async def run_trajectory(harness: str, task: TaskCase, seed: int) -> dict[str, Any]:
    workspace = LiveWorkspace()
    client = TrackingCompletionClient(
        model=f"openai/{CONFIG['served_model']}",
        api_base=API_BASE,
        api_key="local",
        context_window=16_384,
        seed=seed,
        max_tokens=int(CONFIG["max_tokens"]),
        temperature=float(CONFIG["temperature"]),
        top_p=float(CONFIG["top_p"]),
        cache_control_injection_points=[],
    )
    started = time.perf_counter()
    raw_result: Any = None
    exception: str | None = None
    tool_errors = 0
    validation_retries = 0
    try:
        if harness == "json":
            runner = JsonToolHarness(workspace)
            raw_result = await runner.run(task, client)
            tool_errors = runner.tool_errors
            validation_retries = runner.validation_retries
        elif harness == "nooa":
            agent = LiveCapabilityAgent(workspace, llm=client)
            raw_result = await agent.solve(task)
        elif harness == "nooa_no_validation":
            agent = UntypedCapabilityAgent(workspace, llm=client)
            raw_result = await agent.solve(task)
        elif harness == "nooa_serialized":
            agent = SerializedCapabilityAgent(workspace, llm=client)
            raw_result = await agent.solve(task, json.dumps(workspace.snapshot()))
        else:
            raise ValueError(f"unknown harness: {harness}")
    except Exception as exc:  # noqa: BLE001 - exceptions are an outcome metric.
        exception = f"{type(exc).__name__}: {exc}"
    latency = time.perf_counter() - started
    success, failure_class = classify_result(task, raw_result, workspace, exception)
    record = {
        "harness": harness,
        "family": task.family,
        "seed": seed,
        "success": success,
        "failure_class": failure_class,
        "model_calls": client.calls,
        "input_tokens": client.input_tokens,
        "output_tokens": client.output_tokens,
        "total_tokens": client.input_tokens + client.output_tokens,
        "latency_s": round(latency, 3),
        "tool_errors": tool_errors,
        "validation_retries": validation_retries,
        "exception": exception,
        "workspace": workspace.snapshot(),
    }
    await client.aclose()
    print("TRAJECTORY_JSON=" + json.dumps(record, sort_keys=True), flush=True)
    return record


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    families: dict[str, dict[str, Any]] = {}
    for family in sorted({r["family"] for r in records}):
        rows = [r for r in records if r["family"] == family]
        families[family] = {
            "n": len(rows),
            "successes": sum(r["success"] for r in rows),
            "success_rate": sum(r["success"] for r in rows) / len(rows),
            "mean_calls": sum(r["model_calls"] for r in rows) / len(rows),
            "mean_tokens": sum(r["total_tokens"] for r in rows) / len(rows),
            "mean_latency_s": sum(r["latency_s"] for r in rows) / len(rows),
            "failures": {
                failure: sum(r["failure_class"] == failure for r in rows)
                for failure in sorted({r["failure_class"] for r in rows if not r["success"]})
            },
        }
    elapsed = sum(r["latency_s"] for r in records)
    return {
        "schema_version": 1,
        "harness": CONFIG["harness"],
        "model": CONFIG["model"],
        "backend": "kubernetes",
        "gpu_model": "NVIDIA RTX PRO 6000 Blackwell",
        "allocated_gpu_count": int(CONFIG["tensor_parallel_size"]),
        "seeds": CONFIG["seeds"],
        "sampling": {
            "temperature": CONFIG["temperature"],
            "top_p": CONFIG["top_p"],
            "max_turns": CONFIG["max_turns"],
            "max_tokens": CONFIG["max_tokens"],
        },
        "n": len(records),
        "successes": sum(r["success"] for r in records),
        "success_rate": sum(r["success"] for r in records) / len(records),
        "total_model_calls": sum(r["model_calls"] for r in records),
        "total_input_tokens": sum(r["input_tokens"] for r in records),
        "total_output_tokens": sum(r["output_tokens"] for r in records),
        "trajectory_elapsed_s": round(elapsed, 3),
        "families": families,
        "records": records,
    }


def start_server() -> subprocess.Popen[str]:
    command = [
        sys.executable,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        CONFIG["model"],
        "--served-model-name",
        CONFIG["served_model"],
        "--tensor-parallel-size",
        str(CONFIG["tensor_parallel_size"]),
        "--max-model-len",
        "16384",
        "--gpu-memory-utilization",
        "0.86",
        "--enable-auto-tool-choice",
        "--tool-call-parser",
        "hermes",
        "--port",
        "8000",
    ]
    print("SERVER_COMMAND=" + json.dumps(command), flush=True)
    return subprocess.Popen(command, text=True)


def wait_for_server(process: subprocess.Popen[str], timeout_s: int = 3600) -> None:
    deadline = time.monotonic() + timeout_s
    health = "http://127.0.0.1:8000/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"vLLM exited during startup with code {process.returncode}")
        try:
            with urllib.request.urlopen(health, timeout=5) as response:
                if response.status == 200:
                    print("SERVER_READY=1", flush=True)
                    return
        except Exception:
            time.sleep(5)
    raise TimeoutError("vLLM did not become healthy within startup timeout")


async def main() -> None:
    run_started = time.time()
    print(
        "REPRO_CONFIG="
        + json.dumps(
            {
                **CONFIG,
                "backend": "kubernetes",
                "gpu_model": "NVIDIA RTX PRO 6000 Blackwell",
                "common_intent": COMMON_INTENT,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    server = start_server()
    try:
        wait_for_server(server)
        records: list[dict[str, Any]] = []
        for seed in CONFIG["seeds"]:
            for task in make_tasks():
                records.append(await run_trajectory(CONFIG["harness"], task, int(seed)))
        summary = summarize(records)
        summary["run_wall_s"] = round(time.time() - run_started, 3)
        print("REPRO_RESULT_JSON=" + json.dumps(summary, sort_keys=True), flush=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    asyncio.run(main())
