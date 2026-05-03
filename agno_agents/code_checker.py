from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.file import FileTools

from agno_tools.bash_tool import BashTool
from shared.prompts import CODE_CHECKER_SYSTEM_PROMPT

_AGNO_TOOL_DOCS = """\
Tooling (agno tool API):
- `bash(command: str)` runs ONE shell command via `bash -c`. Pipes, &&, redirects, globs
  are supported. Output is prefixed with `EXIT_CODE: <n>` so you can detect failure.
  IMPORTANT: pass commands as ONE STRING, e.g. `bash("./gradlew :app:test")`, NOT as a list.
- `read_file`, `list_files`, `search_files` for file ops (paths relative to project root).

"""

_INSTRUCTIONS = _AGNO_TOOL_DOCS + CODE_CHECKER_SYSTEM_PROMPT


def make_code_checker(project_path: str) -> Agent:
    project = Path(project_path).resolve()
    return Agent(
        name="CodeChecker",
        model=Gemini(
            id="gemini-2.5-flash",
            timeout=180.0,
            retries=1,
            delay_between_retries=1,
        ),
        tools=[
            FileTools(base_dir=project),
            BashTool(base_dir=project, default_timeout=600),
        ],
        instructions=_INSTRUCTIONS,
        tool_call_limit=20,
        markdown=False,
    )
