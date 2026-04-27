from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.file import FileTools

from agno_tools.kotlin_tools import KotlinTools


def make_lint_fix_agent(project_path: str, module: str) -> Agent:
    return Agent(
        name="LintFixAgent",
        model=Gemini(id="gemini-2.5-flash"),
        tools=[
            KotlinTools(project_path=project_path, module=module),
            FileTools(base_dir=Path(project_path)),
        ],
        instructions=f"""
You are a Kotlin code quality expert. The project uses **detekt** (not ktlint).

Workflow:
1. Run detekt for module `{module}` using the run_detekt tool
2. If output starts with "LINT_OK" — output exactly the single token: LINT_OK
3. If output starts with "LINT_ERRORS":
   - Detekt has `autoCorrect = true` — many formatting issues are already fixed on disk; remaining issues are real
   - For each violation, read the offending file with read_file
   - Fix issues by hand (unused imports, magic numbers, complexity, naming, etc.)
   - Save fixed files with save_file
   - Note: do NOT touch generated code or test files unless the violation is genuinely there

IMPORTANT: When detekt is clean, your final output MUST be exactly "LINT_OK" with no extra prose.
""",
        markdown=False,
    )
