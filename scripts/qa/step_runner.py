"""Deadline-enforced step runner (QA-REENGINEERING.md Layer 4).

Every step is (precondition, action, postcondition, deadline, recovery), and
no step may block the suite past its deadline — the failure mode that killed
v1 runs (tap_text hanging 600s inside leave_voice_channel) is structurally
impossible here: callables run in worker threads and the runner abandons them
at the deadline, records a timeout failure, and moves to recovery/abort.

Abandoned threads are daemonic; a hung adb call may linger in the background,
but the runner — and its report — always completes.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

Check = Callable[[], bool]
Action = Callable[[], None]


@dataclass
class Step:
    name: str
    action: Action
    precondition: Optional[Check] = None
    postcondition: Optional[Check] = None
    deadline_s: float = 30.0
    recovery: Optional[Action] = None


@dataclass
class StepResult:
    name: str
    ok: bool
    phase: str  # "pre" | "action" | "post" | "done"
    error: str = ""
    elapsed_s: float = 0.0
    recovered: bool = False


@dataclass
class RunReport:
    ok: bool
    results: list = field(default_factory=list)
    aborted_at: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "ok": self.ok,
                "aborted_at": self.aborted_at,
                "steps": [vars(r) for r in self.results],
            },
            indent=2,
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())


def _call_with_deadline(fn: Callable, deadline_s: float):
    """Run fn in a daemon thread; raise TimeoutError if the deadline passes.

    A daemon thread (not ThreadPoolExecutor, whose __exit__/atexit joins
    workers) is what makes abandonment real: the runner returns at the
    deadline even if fn never does, and a still-hung fn cannot block
    interpreter exit.
    """
    out: queue.Queue = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            out.put(("ok", fn()))
        except BaseException as e:  # noqa: BLE001 — marshal any failure to the caller
            out.put(("err", e))

    threading.Thread(target=worker, daemon=True, name="qa-step").start()
    try:
        kind, value = out.get(timeout=deadline_s)
    except queue.Empty:
        raise TimeoutError(f"deadline {deadline_s}s exceeded") from None
    if kind == "err":
        raise value
    return value


def run_step(step: Step) -> StepResult:
    start = time.monotonic()

    def result(ok: bool, phase: str, error: str = "", recovered: bool = False) -> StepResult:
        return StepResult(step.name, ok, phase, error, time.monotonic() - start, recovered)

    try:
        if step.precondition is not None and not _call_with_deadline(step.precondition, step.deadline_s):
            return result(False, "pre", "precondition returned False")
    except Exception as e:  # noqa: BLE001 — any failure is a step failure, never a crash
        return result(False, "pre", f"{type(e).__name__}: {e}")

    try:
        _call_with_deadline(step.action, step.deadline_s)
    except Exception as e:  # noqa: BLE001
        recovered = _try_recovery(step)
        return result(False, "action", f"{type(e).__name__}: {e}", recovered)

    try:
        if step.postcondition is not None and not _call_with_deadline(step.postcondition, step.deadline_s):
            recovered = _try_recovery(step)
            return result(False, "post", "postcondition returned False", recovered)
    except Exception as e:  # noqa: BLE001
        recovered = _try_recovery(step)
        return result(False, "post", f"{type(e).__name__}: {e}", recovered)

    return result(True, "done")


def _try_recovery(step: Step) -> bool:
    if step.recovery is None:
        return False
    try:
        _call_with_deadline(step.recovery, step.deadline_s)
        return True
    except Exception:  # noqa: BLE001
        return False


def run_steps(steps: list, stop_on_failure: bool = True) -> RunReport:
    report = RunReport(ok=True)
    for step in steps:
        step_result = run_step(step)
        report.results.append(step_result)
        if not step_result.ok:
            report.ok = False
            if stop_on_failure:
                report.aborted_at = step.name
                break
    return report
