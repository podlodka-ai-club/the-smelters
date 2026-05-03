from pathlib import Path

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.tools.file import FileTools

from agno_tools.bash_tool import BashTool
from shared.prompts import ANDROID_CODER_SYSTEM_PROMPT

_AGNO_TOOL_DOCS = """\
Tooling (agno tool API):
- `bash(command: str)` runs ONE shell command via `bash -c`. Pipes, &&, redirects, globs
  are supported. Output is prefixed with `EXIT_CODE: <n>` so you can see exit status.
  IMPORTANT: pass commands as ONE STRING, e.g. `bash("ls -R domain/gifs")`, NOT as a list.
- `read_file`, `save_file`, `list_files`, `search_files`, `search_content` for file ops.
  Paths are relative to the project root.

"""


def _build_instructions(task_content: str) -> str:
    return (
        _AGNO_TOOL_DOCS
        + ANDROID_CODER_SYSTEM_PROMPT
        + "\n\n"
        + "=" * 72
        + "\nTASK SPEC (this is your assignment):\n"
        + "=" * 72
        + "\n\n"
        + task_content.strip()
        + "\n"
    )


def make_android_coder(project_path: str, task_content: str, model: str = "claude") -> Agent:
    """Coder agent. `model` selects the LLM:
       - "claude": Claude Sonnet 4.6 via ANTHROPIC_API_KEY (default, recommended)
       - "gemini": Gemini 2.5 Flash via GOOGLE_API_KEY (cheaper, weaker on multi-file edits)
    """
    project = Path(project_path).resolve()
    if model == "claude":
        llm = Claude(id="claude-sonnet-4-6", max_tokens=16000)
    elif model == "gemini":
        llm = Gemini(
            id="gemini-2.5-flash",
            timeout=180.0,
            retries=1,
            delay_between_retries=1,
        )
    else:
        raise ValueError(f"unknown coder model: {model!r} (expected 'claude' or 'gemini')")
    return Agent(
        name="AndroidCoder",
        model=llm,
        tools=[
            FileTools(base_dir=project),
            BashTool(base_dir=project, default_timeout=300),
        ],
        instructions=_build_instructions(task_content),
        tool_call_limit=40,
        markdown=False,
    )
