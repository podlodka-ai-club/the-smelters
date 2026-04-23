pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "GiphySearch"
include(":app")
include(":core:ui")
include(":core:network")
include(":core:navigation")
include(":data:gifs")
include(":domain:gifs")
include(":testing:gifs")
include(":testing:compose-support")
include(":feature:search")
include(":feature:trending")
include(":feature:details")
include(":feature:gif-ui")
