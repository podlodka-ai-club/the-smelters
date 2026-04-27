import subprocess
from pathlib import Path

from agno.tools import Toolkit


class KotlinTools(Toolkit):
    def __init__(self, project_path: str, module: str):
        super().__init__(name="kotlin_tools", tools=[self.run_detekt, self.run_gradle_test])
        self.project_path = Path(project_path)
        self.module = module if module.startswith(":") else f":{module}"

    def run_detekt(self) -> str:
        """Run detekt on the target Gradle module. Returns lint output."""
        try:
            result = subprocess.run(
                ["./gradlew", f"{self.module}:detekt", "--quiet"],
                capture_output=True,
                text=True,
                cwd=str(self.project_path),
                timeout=180,
            )
            if result.returncode == 0:
                return f"LINT_OK: detekt clean for {self.module}"
            output = (result.stdout + result.stderr).splitlines()
            tail = "\n".join(output[-120:])
            return f"LINT_ERRORS:\n[... last 120 lines ...]\n{tail}"
        except subprocess.TimeoutExpired:
            return "ERROR: detekt timed out after 180s"
        except FileNotFoundError:
            return "ERROR: gradlew not found. Workflow must be invoked with --project pointing at the Gradle root."

    def run_gradle_test(self) -> str:
        """Run unit tests for the target Gradle module."""
        try:
            result = subprocess.run(
                ["./gradlew", f"{self.module}:test", "--quiet"],
                capture_output=True,
                text=True,
                cwd=str(self.project_path),
                timeout=300,
            )
            if result.returncode == 0:
                return f"TESTS_OK: {self.module}:test passed"
            output = (result.stdout + result.stderr).splitlines()
            tail = "\n".join(output[-120:])
            return f"TESTS_FAILED:\n[... last 120 lines ...]\n{tail}"
        except subprocess.TimeoutExpired:
            return "ERROR: gradle test timed out after 300s"
        except FileNotFoundError:
            return "ERROR: gradlew not found."
