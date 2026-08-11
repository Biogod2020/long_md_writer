"""OpenAI Agents SDK adapter that delegates all workspace work to Codex.

All imports from the experimental Codex extension are intentionally isolated in
this module. The rest of the application depends only on ``TaskExecutor`` and
our typed contracts, limiting blast radius when the SDK evolves.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .models import CodexTaskResult, CodexTaskSpec


CODEX_RESULT_OUTPUT_SCHEMA: dict[str, Any] = {
    "title": "CodexTaskResult",
    "description": "Machine-readable result of one bounded workspace task.",
    "properties": [
        {
            "name": "status",
            "description": "completed only when required outputs exist and checks pass",
            "schema": {
                "type": "string",
                "enum": ["completed", "partial", "failed"],
            },
        },
        {
            "name": "summary",
            "description": "Concise description of work performed",
            "schema": {"type": "string"},
        },
        {
            "name": "changed_files",
            "description": "Workspace-relative paths changed",
            "schema": {"type": "array", "items": {"type": "string"}},
        },
        {
            "name": "commands_run",
            "description": "Shell commands executed",
            "schema": {"type": "array", "items": {"type": "string"}},
        },
        {
            "name": "checks",
            "description": "Compact validation outcomes",
            "schema": {"type": "array", "items": {"type": "string"}},
        },
        {
            "name": "unresolved_issues",
            "description": "Remaining issues that prevented full completion",
            "schema": {"type": "array", "items": {"type": "string"}},
        },
    ],
    "required": [
        "status",
        "summary",
        "changed_files",
        "commands_run",
        "checks",
        "unresolved_issues",
    ],
}


EventSink = Callable[[dict[str, Any]], None]


class TaskExecutor(ABC):
    @abstractmethod
    async def execute(self, task: CodexTaskSpec) -> CodexTaskResult:
        raise NotImplementedError


class OpenAICodexExecutor(TaskExecutor):
    """One-turn Agents SDK manager that must call one scoped Codex tool."""

    def __init__(
        self,
        *,
        orchestrator_model: str,
        codex_model: str,
        event_sink: EventSink | None = None,
    ) -> None:
        self.orchestrator_model = orchestrator_model
        self.codex_model = codex_model
        self.event_sink = event_sink

    @staticmethod
    def _controlled_environment(home: Path) -> dict[str, str]:
        """Build an explicit subprocess environment with no ambient secrets."""

        allow = {
            "PATH",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "TMPDIR",
            "TEMP",
            "TMP",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "REQUESTS_CA_BUNDLE",
            "CURL_CA_BUNDLE",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "no_proxy",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
        }
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in allow and value
        }
        environment.update(
            {
                "HOME": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "TERM": "dumb",
                "CI": "1",
                "NO_COLOR": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )
        return environment

    async def _stream_event(self, event: Any) -> None:
        if self.event_sink is None:
            return
        payload: dict[str, Any] = {"event": "codex_stream"}
        raw = getattr(event, "event", event)
        if hasattr(raw, "as_dict"):
            try:
                payload["payload"] = raw.as_dict()
            except Exception:
                payload["payload"] = {"type": type(raw).__name__}
        elif isinstance(raw, Mapping):
            payload["payload"] = dict(raw)
        else:
            payload["payload"] = {"type": type(raw).__name__}
        self.event_sink(payload)

    @staticmethod
    def _parse_output(value: Any) -> CodexTaskResult:
        if isinstance(value, CodexTaskResult):
            return value
        if hasattr(value, "response"):
            value = getattr(value, "response")
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if isinstance(value, Mapping):
            return CodexTaskResult.model_validate(dict(value))
        if not isinstance(value, str):
            value = str(value)
        text = value.strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                return CodexTaskResult(
                    status="failed",
                    summary="Codex returned non-JSON output",
                    unresolved_issues=[text[:1000]],
                )
            payload = json.loads(text[start : end + 1])
        if isinstance(payload, Mapping) and "response" in payload:
            response = payload["response"]
            if isinstance(response, str):
                return OpenAICodexExecutor._parse_output(response)
        return CodexTaskResult.model_validate(payload)

    async def execute(self, task: CodexTaskSpec) -> CodexTaskResult:
        try:
            from agents import Agent, ModelSettings, RunConfig, Runner
            from agents.extensions.experimental.codex import codex_tool
            from agents.models.openai_provider import OpenAIProvider
        except Exception as exc:  # pragma: no cover - exercised in runtime checks
            raise RuntimeError(
                "OpenAI Agents SDK with the experimental Codex extension is required"
            ) from exc

        task.workspace.mkdir(parents=True, exist_ok=True)
        for image in task.local_images:
            resolved = image.resolve(strict=True)
            resolved.relative_to(task.workspace.resolve())

        with tempfile.TemporaryDirectory(prefix="magnum-codex-home-") as temp_home:
            home = Path(temp_home)
            (home / ".codex").mkdir(parents=True, exist_ok=True)
            codex_options: dict[str, Any] = {
                "api_key": os.getenv("CODEX_API_KEY") or os.getenv("OPENAI_API_KEY"),
                "base_url": os.getenv("OPENAI_BASE_URL"),
                "env": self._controlled_environment(home),
                "codex_subprocess_stream_limit_bytes": 16 * 1024 * 1024,
            }
            codex_options = {key: value for key, value in codex_options.items() if value}
            thread_options = {
                "model": self.codex_model,
                "sandbox_mode": task.sandbox_mode,
                "working_directory": str(task.workspace.resolve()),
                "skip_git_repo_check": True,
                "model_reasoning_effort": task.reasoning_effort,
                "network_access_enabled": task.allow_network,
                "web_search_mode": "live" if task.allow_network else "disabled",
                "approval_policy": "never",
            }
            tool = codex_tool(
                name=f"codex_{task.stage.value}",
                description=(
                    "Execute exactly one bounded publication task in the supplied workspace. "
                    "Respect AGENTS.md, allowed paths, required outputs, and validation commands."
                ),
                output_schema=CODEX_RESULT_OUTPUT_SCHEMA,
                codex_options=codex_options,
                default_thread_options=thread_options,
                default_turn_options={"idle_timeout_seconds": task.idle_timeout_seconds},
                persist_session=task.persist_session,
                on_stream=self._stream_event,
            )
            manager = Agent(
                name=f"MagnumOpusManager-{task.stage.value}",
                model=self.orchestrator_model,
                instructions=(
                    "You are a strict dispatcher. Call the available Codex tool exactly once "
                    "with the complete task below. Do not perform the task yourself, do not "
                    "summarize before calling the tool, and stop after the tool returns."
                ),
                tools=[tool],
                model_settings=ModelSettings(tool_choice="required"),
                tool_use_behavior="stop_on_first_tool",
            )
            provider = OpenAIProvider(
                api_key=os.getenv("OPENAI_API_KEY") or os.getenv("CODEX_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
                use_responses=True,
            )
            run_config = RunConfig(
                workflow_name=f"magnum-opus-{task.stage.value}",
                group_id=task.task_id,
                model_provider=provider,
                trace_include_sensitive_data=False,
            )
            inputs: list[dict[str, str]] = [
                {"type": "text", "text": task.prompt, "path": ""}
            ]
            inputs.extend(
                {"type": "local_image", "text": "", "path": str(path.resolve())}
                for path in task.local_images
            )
            dispatch = json.dumps({"inputs": inputs}, ensure_ascii=False)
            try:
                result = await Runner.run(
                    manager,
                    dispatch,
                    max_turns=2,
                    run_config=run_config,
                )
                return self._parse_output(result.final_output)
            finally:
                close = getattr(provider, "aclose", None)
                if close is not None:
                    maybe = close()
                    if isinstance(maybe, Awaitable):
                        await maybe


class FakeExecutor(TaskExecutor):
    """Test executor that records tasks and delegates to an async callback."""

    def __init__(
        self,
        handler: Callable[[CodexTaskSpec], Awaitable[CodexTaskResult]],
    ) -> None:
        self.handler = handler
        self.tasks: list[CodexTaskSpec] = []

    async def execute(self, task: CodexTaskSpec) -> CodexTaskResult:
        self.tasks.append(task)
        return await self.handler(task)
