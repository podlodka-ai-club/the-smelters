import asyncio
import json
import os
from pathlib import Path
from collections.abc import AsyncIterable
import pytest
import sys
import anthropic

from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny
from agents import android_coder

@pytest.fixture
def mock_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "tasks.db"))
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path

def test_get_config(mock_env, monkeypatch):
    # Test fallback
    assert android_coder.get_config() == {"implementation": "claude"}
    
    # Test reading config
    config_data = {"implementation": "gemini", "gemini_api_key": "test_key"}
    (mock_env / "agent_config.json").write_text(json.dumps(config_data))
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
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "gemini", "gemini_api_key": "test"})

    class MockProcess:
        returncode = 0
        async def communicate(self):
            return b'{"ok": true, "summary": "done"}\n', b''
            
    async def mock_exec(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_exec)
    
    assert await android_coder.run_android_coder_agent(1) == 0
    captured = capsys.readouterr()
    assert '"ok": true' in captured.out

@pytest.mark.asyncio
async def test_amain_gemini_no_json(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "gemini"})

    class MockProcess:
        returncode = 0
        async def communicate(self):
            return b'just text\n', b''
            
    async def mock_exec(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_exec)
    
    assert await android_coder.run_android_coder_agent(1) == 0
    captured = capsys.readouterr()
    assert '"ok": true' in captured.out
    assert 'just text' in captured.out

@pytest.mark.asyncio
async def test_amain_gemini_exception(monkeypatch, mock_env, capsys):
    monkeypatch.setattr(android_coder, "generate_prompt_for_task", lambda task_id: f"task:{task_id}")
    monkeypatch.setattr(android_coder, "get_config", lambda: {"implementation": "gemini"})

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
