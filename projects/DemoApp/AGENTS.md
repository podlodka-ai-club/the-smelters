# GiphySearch Developer Agent Guide

This document provides a comprehensive overview of the GiphySearch app architecture, tech stack, and coding conventions to help AI agents and developers contribute effectively.

## 🤖 Agent Setup Requirements

### Prerequisites for Building and Running

Before working with this project, ensure the following are installed and configured:

#### Required Tools
- **JDK 17**: Required for compilation (project centralizes JVM and Java compatibility in root Gradle config)
- **Android SDK**:
  - Compile SDK: API 36
  - Min SDK: API 24
  - Target SDK: API 36
- **Android Command Line Tools**: For building APKs and managing SDK components
- **Gradle Wrapper**: Included in the project (`./gradlew`) - no separate installation needed

#### Environment Setup
- Set `ANDROID_HOME` environment variable to your Android SDK location
- Add Android SDK's `platform-tools` and `tools/bin` to your `PATH`
- Ensure JDK 17 is available in your `PATH` or `JAVA_HOME`

#### Verification Commands
```bash
# Check Java version
java -version  # Should show Java 17

# Check Android SDK
echo $ANDROID_HOME  # Should point to SDK location
sdkmanager --list_installed  # Should show platforms;android-35 and build-tools

# Build the project
./gradlew build

# Run on connected device/emulator
./gradlew installDebug
```

#### API Keys
The app requires a Giphy API key. Set it in `local.properties`:
```
GIPHY_API_KEY=your_api_key_here
```

### 🏗 Architecture

The project follows **Clean Architecture** principles combined with **MVVM** (Model-View-ViewModel) at the presentation layer.

#### Layers
1.  **Data Layer** (`com.aj.giphysearch.data`):
    - `remote`: Ktorfit API interfaces (`GiphyApi`) backed by Ktor `HttpClient`.
    - `dto`: Data Transfer Objects for API responses.
    - `mapper`: Functions to convert DTOs to Domain Models.
    - `repository`: Implementation of domain repository interfaces.
    - `paging`: Paging 3 `PagingSource` implementations.
2.  **Domain Layer** (`com.aj.giphysearch.domain`):
    - `:domain:gifs` is a **pure Kotlin/JVM** library (no Android or Compose runtime). Compose treats `Gif` as stable via [`config/compose-gif-stability.conf`](config/compose-gif-stability.conf), wired once from the root [`build.gradle.kts`](build.gradle.kts) for every subproject that applies the Kotlin Compose plugin.
    - `model`: Pure Kotlin data classes (UI-independent).
    - `repository`: Interface definitions for data access.
    - `usecase`: Single-responsibility business logic classes.
3.  **UI Layer** (`com.aj.giphysearch.ui`):
    - `screens`: Composable functions representing full screens.
    - `viewmodels`: Logic for UI state management using `StateFlow`.
    - `components`: Reusable UI elements (e.g., `GifGrid`).
    - `theme`: Material 3 design tokens.

### 🛠 Tech Stack

- **Language**: Kotlin
- **UI Framework**: Jetpack Compose
- **Asynchronous Programming**: Coroutines & Flow
- **Dependency Injection**: Koin (`viewModelOf`, `factory`, `single`)
- **Networking**: Ktor Client (OkHttp engine) + Ktorfit interface generation (KSP)
- **Serialization**: Kotlinx Serialization
- **Image Loading**: Coil 3 (with GIF and OkHttp support)
- **Navigation**: Jetpack Compose Navigation
- **Pagination**: Paging 3
- **Logging**: Koin Logger & Timber (if applicable)

### ✍️ Coding Conventions & Syntax

#### General
- Use **functional programming** patterns where appropriate (e.g., `map`, `flatMap`).
- Prefer `val` over `var`.
- Use **Trailing Lambda** syntax.
- Ensure all business logic resides in `UseCase`.

#### Kotlin Declaration Placement
- Keep closely related declarations together when it improves readability (for example, route objects in one routes file or a small `UiState` class next to its `ViewModel`).
- Split files when declarations represent different responsibilities, especially for dense files with many top-level types.
- Prefer class-local constants inside a `private companion object` when those constants are only used by that class.
- Use top-level constants only for file-level behavior shared by top-level functions/composables in the same file.
- Keep refactors behavior-preserving: move declarations without changing APIs or business logic unless explicitly requested.

#### ViewModels
- Expose state via `StateFlow` (e.g., `_state` as `MutableStateFlow`, `state` as `StateFlow`).
- Use `viewModelScope` for coroutines.
- Use `viewModelOf(::MyViewModel)` in `AppModule.kt` for DI.

#### UI / Compose
- Use `collectAsStateWithLifecycle()` to observe flows in Composables.
- Keep Composables stateless where possible (pass state down, events up).
- Use `Modifier` as the first optional parameter in Composables.
- Use `AsyncImage` from Coil for remote images.

#### Data Handling
- **Mappers**: Always map DTOs to Domain Models in the Data layer before passing them to the Domain layer.
- **Result Pattern**: Consider using a `Result` or `Resource` wrapper for API calls to handle Success/Error states gracefully.
- **API Definitions**: Define endpoints in Ktorfit interfaces using annotations (`@GET`, `@Query`, `@Path`) and create implementations through DI.
- **Ktorfit Versions**: Keep Ktorfit/KSP versions compatible with the project's Kotlin version before upgrading.

### 🚀 Navigation
- Defined in `com.aj.giphysearch.navigation.AppNavHost`.
- Uses Type-safe navigation where possible or standard route strings.

### 📦 Dependency Injection
- Configuration is in `com.aj.giphysearch.di.AppModule`.
- To add a new dependency:
    1. Define the class.
    2. Register it in `appModule` (e.g., `factory { MyUseCase(get()) }`).

### 🖼 Image Optimization (Crucial)
- The app uses Coil for GIF rendering.
- Preloading logic is often implemented using `remember` and `LaunchedEffect` in the UI to trigger Coil fetches for off-screen items.
- Refer to `PRELOADING_PLAN.md` for performance optimization strategies.

### 📂 Project Structure

#### App Module (`:app`)
```
app/src/main/kotlin/com/aj/giphysearch/
├── di/
│   └── AppModule.kt (Main DI configuration)
├── navigation/
│   └── AppNavHost.kt (Navigation setup)
├── MainActivity.kt (App entry point)
└── GiphyApp.kt (Application class & Koin init)
```

#### Core Module (`:core:ui`)
```
core/ui/src/main/kotlin/com/aj/giphysearch/core/ui/
├── Theme.kt (Shared Material 3 Theme)
├── GifGrid.kt
└── ...
```

#### Other Core Modules
- `navigation`: Type-safe navigation routes.
- `network`: Ktor client configuration.
