"""Central execution receipts. Timings describe executed work, never simulated agents."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
from threading import Lock
from time import perf_counter
from typing import Any, Callable

_ACTIVE: ContextVar[tuple | None] = ContextVar("decision_orchestration", default=None)
_LAST_CALL: ContextVar[str | None] = ContextVar("decision_last_llm_call", default=None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=lambda obj: str(obj) if isinstance(obj, Decimal) else str(obj), allow_nan=False))


def sanitize_llm_messages(messages: list[dict]) -> list[dict]:
    """Redact identifiers BEFORE transport; the audit stores this same sent body."""
    def private_key(key):
        compact = re.sub(r"[^a-z0-9]", "", str(key).lower())
        return compact in {"user", "username", "userid", "documentid", "email", "phone", "mobile", "pan", "pannumber", "folio", "folionumber", "password", "apikey", "accesstoken", "clientid", "demat", "demataccount", "bankaccount", "bankaccountnumber", "accountnumber", "accountlabel", "address", "nominee", "dateofbirth", "dob"} or compact.endswith(("accountnumber", "accesstoken", "apikey"))
    def scrub(value, path=""):
        if isinstance(value, list):
            return [scrub(row, path) for row in value]
        if isinstance(value, dict):
            label = value.get("label") or value.get("field") or ""
            private_fact = bool(re.search(r"\b(?:account|folio|PAN|email|phone|demat|address|birth)\b", str(label), re.I))
            return {key: "[redacted]" if private_key(key) or (private_fact and key == "value") else scrub(item, path+"."+str(key)) for key, item in value.items()}
        return value
    def json_block(match):
        try:
            return "```json\n" + json.dumps(scrub(json.loads(match.group(1))), ensure_ascii=False, indent=2) + "\n```"
        except (ValueError, TypeError):
            return match.group(0)
    output = []
    sensitive_keys = r"(?:folio|folio_number|account_label|account_number|pan|email|phone|mobile|password|access_token|api_key|client_id|user_id|user_name|document_id)"
    for row in messages:
        text = str(row.get("content") or "")
        try:
            text = json.dumps(scrub(json.loads(text)), ensure_ascii=False)
        except (ValueError, TypeError):
            text = re.sub(r"```json\s*(.*?)```", json_block, text, flags=re.S)
        text = re.sub(r'("' + sensitive_keys + r'"\s*:\s*)("(?:[^"\\]|\\.)*"|\d+|null)', r'\1"[redacted]"', text, flags=re.I)
        text = re.sub(r'("user"\s*:\s*)\{[^{}]*\}', r'\1{"identity": "[redacted]"}', text, flags=re.I)
        text = re.sub(r"\b[A-Z]{5}\d{4}[A-Z]\b", "[redacted PAN]", text)
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
        text = re.sub(r"\b(?:sk-proj-|sk-or-v1-|sbp_)[A-Za-z0-9_\-]+", "[redacted credential]", text)
        output.append({"role": str(row.get("role") or "user"), "content": text})
    return output


class OrchestrationRun:
    def __init__(self, run_id: str, objective: str):
        self.run_id, self.objective = run_id, objective
        self.started_at, self._started = _now(), perf_counter()
        self.stages: list[dict] = []
        self.agents: list[dict] = []
        self.llm_calls: list[dict] = []
        self.checks: list[dict] = []
        self._lock = Lock()

    @contextmanager
    def stage(self, identifier: str, label: str, *, depends_on: list[str] | None = None, kind: str = "deterministic", details: Any = None):
        row = {"id": identifier, "label": label, "kind": kind, "status": "running", "started_at": _now(), "depends_on": depends_on or [], "details": details or {}}
        started = perf_counter()
        self.stages.append(row)
        try:
            yield row
            row["status"] = "completed"
        except Exception:
            row["status"] = "failed"
            raise
        finally:
            row.update(finished_at=_now(), duration_ms=round((perf_counter() - started) * 1000, 2))

    @contextmanager
    def scope(self, agent: str):
        token = _ACTIVE.set((self, agent))
        previous = _LAST_CALL.set(None)
        try:
            yield
        finally:
            _LAST_CALL.reset(previous)
            _ACTIVE.reset(token)

    def check(self, identifier: str, passed: bool, detail: str, *, blocking: bool = True):
        self.checks.append({"id": identifier, "passed": bool(passed), "detail": detail, "blocking": blocking})

    def run_parallel(self, tasks: dict[str, dict], *, input_summary: dict) -> dict[str, Any]:
        """Workers receive independent snapshots. No SQLAlchemy session crosses threads."""
        from ai_cio.services.agents.skills_loader import agent_resource_pack
        results: dict[str, Any] = {}

        def execute(identifier, spec):
            started = perf_counter()
            row = {"id": identifier, "label": spec["label"], "status": "running", "started_at": _now(), "execution_mode": spec.get("execution_mode", "deterministic"), "parallel_group": "specialists", "depends_on": ["build_context"], "input_summary": deepcopy(input_summary), "resource_pack": agent_resource_pack(identifier)}
            with self._lock:
                self.agents.append(row)
            with self.scope(identifier):
                try:
                    value = spec["run"]()
                    status = value.get("status") if isinstance(value, dict) else None
                    row["status"] = "disabled" if status == "disabled" else "failed" if status == "error" else "partial" if status in {"partial", "terms_only", "insufficient_data", "unavailable", "not_evaluated", "needs_inputs", "preferences_required"} or isinstance(value, dict) and value.get("available") is False else "completed"
                    row["output_summary"] = {"available": value.get("available"), "status": status, "finding_count": len(value.get("findings") or []), "fund_count": len(value.get("funds") or []), "product_count": len(value.get("catalogue_products") or []), "priced_product_count": len(value.get("eligible_products") or [])} if isinstance(value, dict) else {"analysis_type": type(value).__name__, "observations": len(getattr(value, "observations", []))}
                    return value
                except Exception as exc:
                    row.update(status="failed", error=f"{type(exc).__name__}: specialist could not complete; unsupported results withheld")
                    fallback = spec.get("fallback")
                    return fallback(exc) if callable(fallback) else {"available": False, "status": "error", "agent": identifier, "reason": row["error"]}
                finally:
                    row.update(finished_at=_now(), duration_ms=round((perf_counter() - started) * 1000, 2))

        # Every independent specialist is submitted before any result is joined.
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(tasks))), thread_name_prefix="cio-specialist") as executor:
            futures = {identifier: executor.submit(execute, identifier, spec) for identifier, spec in tasks.items()}
            for identifier, future in futures.items():
                results[identifier] = future.result()
        order = {name: index for index, name in enumerate(tasks)}
        self.agents.sort(key=lambda row: order[row["id"]])
        return results

    def begin_llm(self, agent: str, body: dict, provider: str) -> str:
        with self._lock:
            identifier = f"llm-{len(self.llm_calls) + 1}"
            raw = json.dumps(body, sort_keys=True, ensure_ascii=False)
            self.llm_calls.append({"id": identifier, "agent": agent, "provider": provider, "model": body.get("model"), "status": "running", "started_at": _now(), "purpose": "Explain supplied financial evidence; deterministic services retain calculations and final evidence-backed decisions", "input_fields": ["system instructions and scoped skills", "dated financial facts and constraints", "retrieved evidence or deterministic scenarios"], "request_preview": deepcopy(body), "request_sha256": hashlib.sha256(raw.encode()).hexdigest(), "headers_included": False, "validation": {"json_object": None, "financial_claims": "not independently established by model output"}})
        _LAST_CALL.set(identifier)
        return identifier

    def finish_llm(self, identifier: str, *, started: float, text: str | None = None, error: str | None = None):
        with self._lock:
            row = next(item for item in self.llm_calls if item["id"] == identifier)
            row.update(status="failed" if error else "received", finished_at=_now(), duration_ms=round((perf_counter() - started) * 1000, 2))
            row["response_summary"] = {"characters": len(text or ""), "sha256": hashlib.sha256((text or "").encode()).hexdigest(), "error": error}

    def export(self, *, grounded: list[dict] | None = None) -> dict:
        principles = {p["id"]: p for finding in (grounded or []) for p in (finding.get("proof") or {}).get("principles", []) if p.get("id")}
        used = {p.get("skill") for p in principles.values()}
        packs = [row["resource_pack"] for row in self.agents if row.get("resource_pack")]
        from ai_cio.services.agents.skills_loader import agent_resource_pack
        packs.append(agent_resource_pack("portfolio_agent"))
        failed = [check for check in self.checks if check["blocking"] and not check["passed"]]
        return json_safe({"version": "central-orchestration-v1", "run_id": self.run_id, "objective": self.objective, "status": "failed" if failed else "partial" if any(row["status"] in {"failed", "partial"} for row in self.agents) else "completed", "started_at": self.started_at, "finished_at": _now(), "duration_ms": round((perf_counter() - self._started) * 1000, 2), "stages": self.stages, "agents": self.agents, "llm_calls": self.llm_calls, "validation": {"passed": not failed, "checks": self.checks}, "skills": {"available_packs": packs, "applied_principles": list(principles.values()), "applied_skill_names": sorted(name for name in used if name), "method": "Facts → deterministic calculations → verified skill excerpts → cross-agent constraints → ranked review actions. Supplied references alone do not establish application."}, "parallel_policy": "Independent specialists execute concurrently on copies of one financial snapshot. Evidence validation, action checks, ranking and publication follow the join.", "llm_policy": "The request preview is the redacted body actually sent. Credentials and transport headers are excluded. Model JSON parsing is separate from financial validation. No LLM call is claimed when the transport was not invoked."})


def active_run():
    return _ACTIVE.get()


def note_json_validation(passed: bool):
    active, identifier = _ACTIVE.get(), _LAST_CALL.get()
    if active and identifier:
        run, _ = active
        with run._lock:
            row = next((row for row in run.llm_calls if row["id"] == identifier), None)
            if row:
                row["validation"]["json_object"] = passed
                row["status"] = "completed" if passed else "rejected"


def note_content_validation(checks: dict, accepted: bool):
    active, identifier = _ACTIVE.get(), _LAST_CALL.get()
    if active and identifier:
        run, _ = active
        with run._lock:
            row = next((row for row in run.llm_calls if row["id"] == identifier), None)
            if row:
                row["validation"]["content_checks"] = checks
                row["validation"]["accepted_as_explanation"] = accepted
                if row["status"] != "failed":
                    row["status"] = "completed" if accepted else "rejected"
