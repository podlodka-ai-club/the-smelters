from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.file import FileTools


def make_impl_agent(
    project_path: str,
    package: str,
    class_name: str,
    impl_file_path: str,
    test_file_path: str,
) -> Agent:
    return Agent(
        name="ImplAgent",
        model=Gemini(id="gemini-2.5-flash"),
        tools=[FileTools(base_dir=Path(project_path))],
        instructions=f"""
You are a Kotlin developer working in the GiphySearch Android multi-module project. Given test cases and a test file, write the minimal Kotlin implementation that makes the tests pass.

Process:
1. Use read_file to read the test file at: `{test_file_path}`
2. Identify what needs to be implemented: class shape, methods, constructor params, return types
3. Write the implementation

Rules:
- Package declaration: `package {package}`
- Class name: `{class_name}`
- Save to EXACTLY this path (relative to project root): `{impl_file_path}`
- Idiomatic Kotlin: prefer `val`, data classes for value types, sealed types for closed hierarchies
- YAGNI — implement only what the tests require
- If the test imports types from this codebase (e.g. `com.aj.giphysearch.domain.gifs.*`), use those types as-is — do NOT recreate them
- Use coroutines and Flow where the test signatures require them
- Save with save_file tool

After saving, output the exact file path on a line starting with "FILE_PATH: "
""",
        markdown=False,
    )
