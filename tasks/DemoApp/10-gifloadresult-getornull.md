Project: DemoApp

# Add `GifLoadResult.getOrNull()` extension

## Summary

- Priority: Low (smoke test for the orchestrator pipeline)
- Estimated Duration: <5 minutes
- Complexity: Trivial
- User Impact: Internal (consumer ergonomics)

## Context

`GifLoadResult<T>` is a sealed type used by repository / use-case layers to model
"this load either succeeded with data, or failed with a typed `GifDomainError`":

```kotlin
sealed class GifLoadResult<out T> {
    data class Success<T>(val data: T) : GifLoadResult<T>()
    data class Failure(val error: GifDomainError) : GifLoadResult<Nothing>()
}
```

Today callers extract data with a `when` block. A small `.getOrNull()` extension —
mirroring Kotlin's standard `Result.getOrNull()` — turns "best-effort read" calls
into one-liners and reduces ceremony at call sites that don't care about the
error.

## Acceptance

- A top-level extension `fun <T> GifLoadResult<T>.getOrNull(): T?` is added.
- For `GifLoadResult.Success(data)` it returns `data`.
- For `GifLoadResult.Failure(_)` it returns `null`.
- Unit tests cover both branches.
- All tests pass via `./gradlew :domain:gifs:test`.
- No existing tests break.
- No callers of `GifLoadResult` are modified (this is a pure addition).

## Technical Notes

- **Module:** `:domain:gifs` (pure Kotlin/JVM — uses the `kotlin-jvm` plugin, NOT Android).
- **Package:** `com.aj.giphysearch.domain.gifs.error` (same as `GifLoadResult`).
- **Test framework:** JUnit 4 (already in this module's `build.gradle.kts`).
- **File location:** either inline at the bottom of
  `domain/gifs/src/main/kotlin/com/aj/giphysearch/domain/gifs/error/GifLoadResult.kt`,
  OR a new file `GifLoadResultExt.kt` in the same directory. Pick one.
- **Test location:** `domain/gifs/src/test/kotlin/com/aj/giphysearch/domain/gifs/error/GifLoadResultExtensionsTest.kt`.
- Existing types you may reference in tests:
  - `GifLoadResult.Success(data)` and `GifLoadResult.Failure(error)`.
  - `GifDomainError.Unknown` (an object) and `GifDomainError.RateLimited` (an object).
  - For `T` in tests, use `String` or `Int` — no need to construct `Gif` instances.

## Suggested test cases (you may add more — these are the minimum)

1. `getOrNull on Success returns the wrapped data`
   - Given `val r: GifLoadResult<String> = GifLoadResult.Success("hello")`
   - Expect `r.getOrNull() == "hello"`
2. `getOrNull on Failure returns null`
   - Given `val r: GifLoadResult<String> = GifLoadResult.Failure(GifDomainError.Unknown)`
   - Expect `r.getOrNull() == null`
3. `getOrNull preserves the type parameter`
   - Given `val r: GifLoadResult<List<Int>> = GifLoadResult.Success(listOf(1, 2, 3))`
   - Expect `r.getOrNull() == listOf(1, 2, 3)` (and the result is a `List<Int>?`).

## Out of scope

- Do NOT modify any callers of `GifLoadResult` (no refactor of repository / use-case code).
- Do NOT add `getOrThrow()`, `map`, `fold`, `onSuccess`, `onFailure`, etc. — only
  `getOrNull()`.
- No Compose, no Android, no DI, no new modules.
- No changes to `GifLoadResult` itself (sealed class declaration stays as-is).

## RUN_TESTS.sh

The script you generate at the project root must run exactly:

```bash
#!/usr/bin/env bash
set -e
./gradlew :domain:gifs:test --quiet
```
