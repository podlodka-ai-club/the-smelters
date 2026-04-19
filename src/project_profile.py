from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectProfile:
    name: str
    label: str
    default_test_command: str
    coder_verification: str
    reviewer_verification: str


PYTHON_PROFILE = ProjectProfile(
    name="python",
    label="Python",
    default_test_command="pytest",
    coder_verification=(
        "Prefer the narrowest failing test first, then run `pytest` for the full suite."
    ),
    reviewer_verification=(
        "Run `pytest`, then inspect `git diff main...HEAD` and reject unrelated changes."
    ),
)

ANDROID_PROFILE = ProjectProfile(
    name="android",
    label="Android (Gradle)",
    default_test_command="./gradlew testDebugUnitTest",
    coder_verification=(
        "Start with the narrowest relevant Gradle task, usually `./gradlew testDebugUnitTest`. "
        "If the change touches app wiring or manifests, also run `./gradlew assembleDebug`."
    ),
    reviewer_verification=(
        "Run `./gradlew testDebugUnitTest`, and when the change is broader than unit logic also "
        "run `./gradlew assembleDebug`. Then inspect `git diff main...HEAD` for scope control."
    ),
)

GENERIC_PROFILE = ProjectProfile(
    name="generic",
    label="Generic repository",
    default_test_command="project-specific test command",
    coder_verification=(
        "Run the narrowest project-specific verification first, then the standard repo test command."
    ),
    reviewer_verification=(
        "Run the project's standard verification command, then inspect `git diff main...HEAD`."
    ),
)


def detect_project_profile(repo_root: Path) -> ProjectProfile:
    android_markers = (
        repo_root / "gradlew",
        repo_root / "settings.gradle",
        repo_root / "settings.gradle.kts",
        repo_root / "app" / "build.gradle",
        repo_root / "app" / "build.gradle.kts",
    )
    if any(marker.exists() for marker in android_markers):
        return ANDROID_PROFILE

    python_markers = (
        repo_root / "pyproject.toml",
        repo_root / "requirements.txt",
        repo_root / "pytest.ini",
    )
    if any(marker.exists() for marker in python_markers):
        return PYTHON_PROFILE

    return GENERIC_PROFILE
