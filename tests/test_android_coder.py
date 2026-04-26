import asyncio
import json
import os
from pathlib import Path
from collections.abc import AsyncIterable
import pytest
import sys
import anthropic
import yaml

from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny
from agents import android_coder
from src.tracker import Tracker


@pytest.fixture
def mock_env(monkeypatch, tmp_path):
    db_dir = tmp_path / "database" / "DemoApp"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "tasks.db"
    monkeypatch.setenv("TRACKER_DB", str(db_path))
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))

    tracker = Tracker(db_path)
    tracker.init_schema()
    row_id = tracker.insert_task(
        task_number=1,
        title="Fixture task",
        spec_path="tasks/DemoApp/1-spec.md",
    )
    assert row_id == 1

    spec_dir = tmp_path / "tasks" / "DemoApp"
    spec_dir.mkdir(parents=True)
    (spec_dir / "1-spec.md").write_text("# spec\n", encoding="utf-8")

    proj = tmp_path / "projects" / "DemoApp"
    proj.mkdir(parents=True)
    (proj / "README.md").write_text("stub\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    return tmp_path

def test_get_config(mock_env, monkeypatch):
    # Test fallback
    assert android_coder.get_config() == {
        "implementation": "gemini",
        "agent_timeout": 7200,
        "agent_inactivity_timeout": 600,
    }
    
    # Test reading config
    config_data = {"implementation": "gemini", "gemini_api_key": "test_key", "agent_timeout": 3600}
    (mock_env / "agent_config.yml").write_text(yaml.dump(config_data))
    assert android_coder.get_config() == config_data

@pytest.mark.asyncio
async def test_can_use_tool():
    # Test allowed tool
    assert isinstance(await android_coder.validate_tool_usage("Read", {}, None), PermissionResultAllow)
    
    # Test allowed bash
    assert isinstance(await android_coder.validate_tool_usage("Bash", {"command": "ls"}, None), PermissionResultAllow)
    
    # Test denied bash
    assert isinstance(await android_coder.validate_tool_usage("Bash", {"command": "rm -rf /"}, None), PermissionResultDeny)
    assert isinstance(await android_coder.validate_tool_usage("Bash", {"command": "git push"}, None), PermissionResultDeny)
    assert isinstance(await android_coder.validate_tool_usage("Bash", {"command": "git commit -m test"}, None), PermissionResultDeny)

def test_extract_text():
    class MsgResult:
        result = "test result"
    class MsgText:
        text = "test text"
    class MsgEmpty:
        pass
    
    assert android_coder.extract_text_from_message(MsgResult()) == "test result"
    assert android_coder.extract_text_from_message(MsgText()) == "test text"
    assert android_coder.extract_text_from_message(MsgEmpty()) == ""


def test_extract_success_json_from_output():
    output = "\n".join(
        [
            "tool log line",
            '{"ok": true, "summary": "done", "script_generated": "RUN_TESTS.sh"}',
            "final non-json line",
        ]
    )
    payload = android_coder.extract_success_json_from_output(output)
    assert payload is not None
    assert payload["ok"] is True
    assert payload["script_generated"] == "RUN_TESTS.sh"


def test_extract_success_json_from_output_missing_script():
    output = '{"ok": true, "summary": "done"}'
    assert android_coder.extract_success_json_from_output(output) is None


def test_extract_success_json_from_output_multiline_object():
    output = """
log line
{
  "ok": true,
  "summary": "done",
  "script_generated": "RUN_TESTS.sh"
}
trailing line
"""
    payload = android_coder.extract_success_json_from_output(output)
    assert payload is not None
    assert payload["ok"] is True
    assert payload["script_generated"] == "RUN_TESTS.sh"

@pytest.mark.asyncio
async def test_streaming_prompt():
    stream = android_coder.stream_prompt_messages("test prompt")
    items = [item async for item in stream]
    assert len(items) == 1
    assert items[0]["message"]["content"] == "test prompt"

def test_load_task_and_build_prompt(mock_env, monkeypatch):
    class MockTracker:
        def __init__(self, db_path): pass
        def get_task(self, task_id):
            class Row:
                task_number = 1
                title = "Test Task"
                spec_path = "test.md"
                review_notes = "fix this"
            return Row()

    monkeypatch.setattr(android_coder, "Tracker", MockTracker)
    (mock_env / "test.md").write_text("Test Spec Body")
    
    class MockProfile:
        label = "test profile"
    monkeypatch.setattr(android_coder, "detect_project_profile", lambda p: MockProfile())
    
    # mock subprocess
    import subprocess
    monkeypatch.setattr(subprocess, "check_output", lambda *args, **kwargs: "test diff")
    
    prompt = android_coder.generate_prompt_for_task(1)
    assert "Test Task" in prompt
    assert "Test Spec Body" in prompt
    assert "fix this" in prompt
    assert "test diff" in prompt

    # mock subprocess fail
    def raise_err(*args, **kwargs): raise Exception("fail")
    monkeypatch.setattr(subprocess, "check_output", raise_err)
    prompt2 = android_coder.generate_prompt_for_task(1)
    assert "test diff" not in prompt2


@pytest.mark.asyncio
async def test_amain_claude(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "claude"})

    async def fake_query(*, prompt, options):
        class Msg:
            result = '{"ok": true, "summary": "done"}'
            tool_use = type('obj', (object,), {'name': 'Bash', 'input': {'command': 'gradlew assembleDebug'}})()
        yield Msg()

    monkeypatch.setattr(android_coder, "query", fake_query)
    
    assert await android_coder.run_android_coder_agent(1) == 0
    captured = capsys.readouterr()
    assert '"ok": true' in captured.out

@pytest.mark.asyncio
async def test_amain_claude_no_json(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "claude", "anthropic_api_key": "test"})

    async def fake_query(*, prompt, options):
        class Msg:
            text = 'just text'
            tool_use = type('obj', (object,), {'name': 'Write', 'input': {'filePath': 'test.txt'}})()
        yield Msg()

    monkeypatch.setattr(android_coder, "query", fake_query)
    
    assert await android_coder.run_android_coder_agent(1) == 0
    captured = capsys.readouterr()
    assert '"ok": true' in captured.out
    assert 'just text' in captured.out

@pytest.mark.asyncio
async def test_amain_claude_rate_limit(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "claude"})

    class DummyRequest:
        pass
    class DummyResponse:
        request = DummyRequest()
        status_code = 400
        headers = {}

    calls = 0
    async def fake_query(*, prompt, options):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise anthropic.RateLimitError("rate limit", response=DummyResponse(), body=None)
        if calls == 2:
            raise anthropic.APIConnectionError(message="conn err", request=DummyRequest())
        class Msg:
            text = '{"ok": true, "summary": "done"}'
        yield Msg()

    monkeypatch.setattr(android_coder, "query", fake_query)
    async def mock_sleep(x): pass
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    
    assert await android_coder.run_android_coder_agent(1) == 0
    assert calls == 3

@pytest.mark.asyncio
async def test_amain_claude_bad_request(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "claude"})
    
    class DummyRequest: pass
    class DummyResponse:
        request = DummyRequest()
        status_code = 400
        headers = {}
    
    async def fake_query(*, prompt, options):
        if False: yield
        raise anthropic.BadRequestError("context_length_exceeded", response=DummyResponse(), body=None)

    monkeypatch.setattr(android_coder, "query", fake_query)
    
    assert await android_coder.run_android_coder_agent(1) == 1
    captured = capsys.readouterr()
    assert "Context window exceeded" in captured.out

@pytest.mark.asyncio
async def test_amain_claude_bad_request_other(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "claude"})
    
    class DummyRequest: pass
    class DummyResponse:
        request = DummyRequest()
        status_code = 400
        headers = {}

    async def fake_query(*, prompt, options):
        if False: yield
        raise anthropic.BadRequestError("other error", response=DummyResponse(), body=None)

    monkeypatch.setattr(android_coder, "query", fake_query)
    
    with pytest.raises(anthropic.BadRequestError):
        await android_coder.run_android_coder_agent(1)

@pytest.mark.asyncio
async def test_amain_claude_exception(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "claude"})
    
    async def fake_query(*, prompt, options):
        if False: yield
        raise ValueError("test val err")

    monkeypatch.setattr(android_coder, "query", fake_query)
    
    assert await android_coder.run_android_coder_agent(1) == 1
    captured = capsys.readouterr()
    assert "test val err" in captured.out

@pytest.mark.asyncio
async def test_amain_gemini(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "gemini", "gemini_api_key": "test", "agent_timeout": 7200})
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")
    async def mock_verify(*args, **kwargs):
        return True
    
    monkeypatch.setattr(android_coder, "verify_build_compiles", mock_verify)
    monkeypatch.setenv("SKIP_RUN_TESTS_CHECK", "1")
    query_called = False
    async def should_not_call_query(*, prompt, options):
        nonlocal query_called
        query_called = True
        if False:
            yield
    monkeypatch.setattr(android_coder, "query", should_not_call_query)

    class MockProcess:
        returncode = 0
        pid = 12345
        stdin = None
        stdout = None
        stderr = None
        async def communicate(self):
            return b'{"ok": true, "summary": "done"}\n', b''
            
    async def mock_exec(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_exec)
    
    assert await android_coder.run_android_coder_agent(1) == 0
    assert query_called is False
    captured = capsys.readouterr()
    assert '"ok": true' in captured.out


@pytest.mark.asyncio
async def test_opencode_cmd_shape_no_positional_with_file(monkeypatch, mock_env):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(
        android_coder,
        "get_config",
        lambda: {"implementation": "gemini", "agent_timeout": 7200, "agent_inactivity_timeout": 600},
    )
    monkeypatch.setattr(android_coder, "verify_build_compiles", lambda *args, **kwargs: asyncio.sleep(0, result=True))
    monkeypatch.setenv("SKIP_RUN_TESTS_CHECK", "1")
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")

    captured_cmd: list[str] = []

    class MockProcess:
        returncode = 0
        pid = 12345
        stdout = None
        stderr = None
        async def communicate(self):
            return b'{"ok": true, "summary": "done"}\n', b""

    async def process_factory(*args, **kwargs):
        if args and args[0] == "opencode":
            captured_cmd.extend(args)
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", process_factory)

    assert await android_coder.run_android_coder_agent(1) == 0
    assert captured_cmd[0:2] == ["opencode", "run"]
    assert "--file" in captured_cmd
    assert "implement task" not in captured_cmd
    assert "Implement the task exactly as described in the attached prompt file." in captured_cmd


@pytest.mark.asyncio
async def test_opencode_subprocess_stdin_devnull(monkeypatch, mock_env):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(
        android_coder,
        "get_config",
        lambda: {"implementation": "gemini", "agent_timeout": 7200, "agent_inactivity_timeout": 600},
    )
    monkeypatch.setattr(android_coder, "verify_build_compiles", lambda *args, **kwargs: asyncio.sleep(0, result=True))
    monkeypatch.setenv("SKIP_RUN_TESTS_CHECK", "1")
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")

    opencode_kwargs: dict[str, object] = {}

    class MockProcess:
        returncode = 0
        pid = 12345
        stdout = None
        stderr = None
        async def communicate(self):
            return b'{"ok": true, "summary": "done"}\n', b""

    async def process_factory(*args, **kwargs):
        if args and args[0] == "opencode":
            opencode_kwargs.update(kwargs)
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", process_factory)

    assert await android_coder.run_android_coder_agent(1) == 0
    assert opencode_kwargs.get("stdin") is asyncio.subprocess.DEVNULL


@pytest.mark.asyncio
async def test_agent_launch_event_emitted(monkeypatch, mock_env):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(
        android_coder,
        "get_config",
        lambda: {"implementation": "gemini", "agent_timeout": 7200, "agent_inactivity_timeout": 600},
    )
    monkeypatch.setattr(android_coder, "verify_build_compiles", lambda *args, **kwargs: asyncio.sleep(0, result=True))
    monkeypatch.setenv("SKIP_RUN_TESTS_CHECK", "1")
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")

    events: list[dict[str, object]] = []
    monkeypatch.setattr(android_coder, "emit_event", lambda *_args, **kwargs: events.append(kwargs))

    class MockProcess:
        returncode = 0
        pid = 12345
        stdout = None
        stderr = None
        async def communicate(self):
            return b'{"ok": true, "summary": "done"}\n', b""

    async def process_factory(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", process_factory)

    assert await android_coder.run_android_coder_agent(1) == 0
    launch_events = [event for event in events if event.get("type") == "agent_launch"]
    assert launch_events, "Expected agent_launch event"
    launch = launch_events[-1]
    assert launch.get("cmd")
    assert launch.get("cwd")
    assert launch.get("model")
    assert launch.get("server_health") == "http_200"


class _ProcessWithStreamingStdout:
    def __init__(self, lines: list[str], exit_delay: float, returncode: int = 0):
        self.returncode: int | None = None
        self.pid = 12345
        self.stdin = None
        self.stderr = None
        self._lines = list(lines)
        self._line_idx = 0
        self._exit_delay = exit_delay
        self._target_returncode = returncode
        self._done = asyncio.Event()
        self.stdout = self._Stdout(self)

    class _Stdout:
        def __init__(self, owner):
            self.owner = owner
            self._buf = b""

        async def _extend_buf(self) -> None:
            while not self._buf:
                if self.owner._line_idx < len(self.owner._lines):
                    line = self.owner._lines[self.owner._line_idx]
                    self.owner._line_idx += 1
                    self._buf += f"{line}\n".encode("utf-8")
                elif self.owner.returncode is not None:
                    return
                else:
                    await asyncio.sleep(0.01)

        async def read(self, n: int) -> bytes:
            if n <= 0:
                n = 1024
            await self._extend_buf()
            if not self._buf:
                return b""
            chunk = self._buf[:n]
            self._buf = self._buf[n:]
            return chunk

        async def readline(self):
            await self._extend_buf()
            if not self._buf:
                while self.owner.returncode is None:
                    await asyncio.sleep(0.01)
                return b""
            if b"\n" in self._buf:
                i = self._buf.index(b"\n") + 1
                line, self._buf = self._buf[:i], self._buf[i:]
                return line
            line, self._buf = self._buf, b""
            return line

    async def wait(self):
        if self.returncode is None:
            await asyncio.sleep(self._exit_delay)
            if self.returncode is None:
                self.returncode = self._target_returncode
        self._done.set()
        return self.returncode

    def kill(self):
        self.returncode = -9
        self._done.set()

    async def communicate(self):
        await self.wait()
        return b"", b""


@pytest.mark.asyncio
async def test_amain_gemini_inactivity_timeout(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(
        android_coder,
        "get_config",
        lambda: {"implementation": "gemini", "agent_timeout": 30, "agent_inactivity_timeout": 1},
    )
    monkeypatch.setattr(android_coder, "verify_build_compiles", lambda *args, **kwargs: asyncio.sleep(0, result=True))
    monkeypatch.setenv("SKIP_RUN_TESTS_CHECK", "1")
    monkeypatch.setattr(android_coder, "HEARTBEAT_INTERVAL_SECONDS", 1)
    monkeypatch.setattr(android_coder, "WATCHDOG_POLL_SECONDS", 0.1)
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")

    events: list[dict[str, object]] = []
    monkeypatch.setattr(android_coder, "emit_event", lambda *_args, **kwargs: events.append(kwargs))

    calls = 0
    async def process_factory(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            proc = _ProcessWithStreamingStdout([], exit_delay=0, returncode=0)
            proc.communicate = lambda: asyncio.sleep(0, result=(b"same-sha\n", b""))  # type: ignore[method-assign]
            return proc
        if calls == 2:
            return _ProcessWithStreamingStdout(["first line"], exit_delay=10)
        proc = _ProcessWithStreamingStdout([], exit_delay=0, returncode=0)
        proc.communicate = lambda: asyncio.sleep(0, result=(b"same-sha\n", b""))  # type: ignore[method-assign]
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", process_factory)

    assert await android_coder.run_android_coder_agent(1) == 1
    captured = capsys.readouterr()
    assert "Agent inactive for" in captured.out
    assert "Agent timed out after" not in captured.out
    inactivity_events = [event for event in events if event.get("error") == "inactivity_timeout"]
    assert inactivity_events


@pytest.mark.asyncio
async def test_amain_gemini_heartbeat(monkeypatch, mock_env):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(
        android_coder,
        "get_config",
        lambda: {"implementation": "gemini", "agent_timeout": 30, "agent_inactivity_timeout": 10},
    )
    monkeypatch.setattr(android_coder, "verify_build_compiles", lambda *args, **kwargs: asyncio.sleep(0, result=True))
    monkeypatch.setenv("SKIP_RUN_TESTS_CHECK", "1")
    monkeypatch.setattr(android_coder, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(android_coder, "WATCHDOG_POLL_SECONDS", 0.1)
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")

    events: list[dict[str, object]] = []
    monkeypatch.setattr(android_coder, "emit_event", lambda *_args, **kwargs: events.append(kwargs))

    calls = 0
    async def process_factory(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls in (1, 3):
            proc = _ProcessWithStreamingStdout([], exit_delay=0, returncode=0)
            proc.communicate = lambda: asyncio.sleep(0, result=(b"same-sha\n", b""))  # type: ignore[method-assign]
            return proc
        return _ProcessWithStreamingStdout(["working"], exit_delay=0.05, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", process_factory)

    assert await android_coder.run_android_coder_agent(1) == 0
    heartbeat_events = [event for event in events if event.get("type") == "agent_heartbeat"]
    assert heartbeat_events


@pytest.mark.asyncio
async def test_opencode_error_pattern_detected(monkeypatch, mock_env):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(
        android_coder,
        "get_config",
        lambda: {"implementation": "gemini", "agent_timeout": 30, "agent_inactivity_timeout": 10},
    )
    monkeypatch.setattr(android_coder, "verify_build_compiles", lambda *args, **kwargs: asyncio.sleep(0, result=True))
    monkeypatch.setenv("SKIP_RUN_TESTS_CHECK", "1")
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")

    events: list[dict[str, object]] = []
    monkeypatch.setattr(android_coder, "emit_event", lambda *_args, **kwargs: events.append(kwargs))

    calls = 0
    async def process_factory(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls in (1, 3):
            proc = _ProcessWithStreamingStdout([], exit_delay=0, returncode=0)
            proc.communicate = lambda: asyncio.sleep(0, result=(b"same-sha\n", b""))  # type: ignore[method-assign]
            return proc
        return _ProcessWithStreamingStdout(
            ["Error: User location is not supported for the API use."],
            exit_delay=0.01,
            returncode=0,
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", process_factory)

    assert await android_coder.run_android_coder_agent(1) == 0
    detected = [event for event in events if event.get("type") == "opencode_error_detected"]
    assert detected
    assert detected[-1].get("category") == "location_unsupported"

@pytest.mark.asyncio
async def test_amain_gemini_no_json(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "gemini", "agent_timeout": 7200})
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")
    async def mock_verify(*args, **kwargs):
        return True
    monkeypatch.setattr(android_coder, "verify_build_compiles", mock_verify)

    class MockProcess:
        returncode = 0
        pid = 12345
        stdin = None
        stdout = None
        stderr = None
        async def communicate(self):
            return b'just text\n', b''
            
    async def mock_exec(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_exec)
    monkeypatch.setenv("SKIP_RUN_TESTS_CHECK", "1")  # Skip file check
    
    assert await android_coder.run_android_coder_agent(1) == 0
    captured = capsys.readouterr()
    assert 'just text' in captured.out


@pytest.mark.asyncio
async def test_amain_gemini_missing_run_tests_sh(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "gemini", "agent_timeout": 7200})
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")
    async def mock_verify(*args, **kwargs):
        return True
    monkeypatch.setattr(android_coder, "verify_build_compiles", mock_verify)
    monkeypatch.delenv("SKIP_RUN_TESTS_CHECK", raising=False)

    class MockProcess:
        returncode = 0
        pid = 12345
        stdin = None
        stdout = None
        stderr = None
        async def communicate(self):
            return b'{"ok": true, "summary": "done", "script_generated": "RUN_TESTS.sh"}\n', b''

    async def process_factory(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", process_factory)

    assert await android_coder.run_android_coder_agent(1) == 1
    captured = capsys.readouterr()
    assert "RUN_TESTS.sh was not created" in captured.out


@pytest.mark.asyncio
async def test_amain_gemini_auto_commit_detected(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "gemini", "agent_timeout": 7200})
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")
    monkeypatch.setattr(android_coder, "verify_build_compiles", lambda *a, **k: asyncio.sleep(0, result=True))
    monkeypatch.setenv("SKIP_RUN_TESTS_CHECK", "1")

    class MockProcess:
        returncode = 0
        pid = 12345
        stdin = None
        stdout = None
        stderr = None
        def __init__(self, output: bytes):
            self._output = output
        async def communicate(self):
            return self._output, b""

    calls = 0
    async def process_factory(*args, **kwargs):
        nonlocal calls
        calls += 1
        # pre-run git rev-parse
        if calls == 1:
            return MockProcess(b"pre123\n")
        # opencode run
        if calls == 2:
            return MockProcess(b'{"ok": true, "summary": "done", "script_generated": "RUN_TESTS.sh"}\n')
        # post-run git rev-parse
        return MockProcess(b"post999\n")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", process_factory)

    assert await android_coder.run_android_coder_agent(1) == 1
    captured = capsys.readouterr()
    assert "Auto commit detected" in captured.out

@pytest.mark.asyncio
async def test_amain_gemini_exception(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "gemini"})
    monkeypatch.setattr(android_coder, "get_opencode_version", lambda: "test-version")
    monkeypatch.setattr(android_coder, "get_server_health", lambda: "http_200")

    async def mock_exec(*args, **kwargs):
        raise ValueError("test err")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_exec)
    
    assert await android_coder.run_android_coder_agent(1) == 1
    captured = capsys.readouterr()
    assert "test err" in captured.out

def test_main(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "1"])
    async def fake_amain(task_id):
        assert task_id == 1
        return 42
    monkeypatch.setattr(android_coder, "run_android_coder_agent", fake_amain)
    assert android_coder.main() == 42
