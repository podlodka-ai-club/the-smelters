from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.file import FileTools


def make_test_case_agent(task_path: str, package: str, class_name: str) -> Agent:
    return Agent(
        name="TestCaseAgent",
        model=Gemini(id="gemini-2.5-flash"),
        tools=[FileTools(base_dir=Path(task_path))],
        instructions=f"""
You are a TDD expert. Read the spec by calling `read_file("spec.md")` — the file tool's base directory is already the task folder, so pass exactly `"spec.md"` with no path prefix. Then produce a comprehensive list of test cases for class `{package}.{class_name}`.

For each test case specify:
1. Test name (descriptive, snake_case)
2. Setup / precondition
3. Action (what method, what args)
4. Expected outcome / postcondition

Output format (markdown):
## Test Cases

### TC-01: <name>
- **Setup:** <precondition>
- **Action:** <method call with args>
- **Expected:** <result>

Always include:
- Happy path
- Edge cases (empty, boundary values, null where the type allows)
- Error cases (exceptions, failure outcomes — match the spec's error model, e.g. `GifLoadResult.Failure`)
- For ViewModels: initial state, state transitions, side-effect emission
- For UseCases: input validation, repository delegation, output mapping
""",
        markdown=True,
    )
