from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.file import FileTools


def make_test_writer_agent(
    project_path: str,
    package: str,
    class_name: str,
    test_file_path: str,
) -> Agent:
    return Agent(
        name="TestWriterAgent",
        model=Gemini(id="gemini-2.5-flash"),
        tools=[FileTools(base_dir=Path(project_path))],
        instructions=f"""
You are a Kotlin TDD expert. Given a list of test cases, write a complete JUnit4 test file for the GiphySearch Android project.

Required imports (use only what you need):
    import org.junit.Test
    import org.junit.Assert.assertEquals
    import org.junit.Assert.assertTrue
    import org.junit.Assert.assertFalse
    import org.junit.Assert.assertNotNull
    import org.junit.Assert.assertNull
    import org.junit.Before
    import org.junit.After
    import kotlinx.coroutines.test.runTest
    import kotlinx.coroutines.test.StandardTestDispatcher
    import kotlinx.coroutines.test.advanceUntilIdle
    import app.cash.turbine.test  // ONLY when testing kotlinx.coroutines.flow.Flow / StateFlow

Rules:
- Package declaration: `package {package}`
- Class name: `{class_name}Test`
- Save to EXACTLY this path (relative to project root): `{test_file_path}`
- The class under test does not exist yet — that is OK. Add: `import {package}.{class_name}`
- Use `runTest {{ ... }}` for suspend functions
- Test method names: `fun \\`when input X then result Y\\`()` (backtick-quoted, descriptive)
- For Flow/StateFlow tests use Turbine: `viewModel.someFlow.test {{ awaitItem() ... cancelAndConsumeRemainingEvents() }}`
- Forbidden: JUnit5 imports (`org.junit.jupiter.*`), `@BeforeEach`, `@AfterEach`, `assertThrows` from JUnit5, `kotlin.test.*`
- Save the file using the save_file tool with the exact path above

After saving, output the exact file path on a line starting with "FILE_PATH: "
""",
        markdown=False,
    )
