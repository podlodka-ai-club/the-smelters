from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.file import FileTools

from agno_tools.kotlin_tools import KotlinTools


def make_test_run_agent(
    project_path: str,
    module: str,
    impl_file_path: str,
) -> Agent:
    return Agent(
        name="TestRunAgent",
        model=Gemini(id="gemini-2.5-flash"),
        tools=[
            KotlinTools(project_path=project_path, module=module),
            FileTools(base_dir=Path(project_path)),
        ],
        instructions=f"""
You are a Kotlin TDD expert. Run tests for module `{module}` and fix the implementation when they fail.

Workflow:
1. Run tests using the run_gradle_test tool (it executes `:module:test`)
2. If output starts with "TESTS_OK" — output exactly the single token: TESTS_OK
3. If output starts with "TESTS_FAILED":
   - Read the failure output carefully — note the assertion that failed and the values it saw
   - Read the implementation at: `{impl_file_path}`
   - Decide the smallest correct change. Do NOT modify test files.
   - Save the corrected implementation with save_file

IMPORTANT: When all tests pass, your final output MUST be exactly "TESTS_OK" with no extra prose.
""",
        markdown=False,
    )
