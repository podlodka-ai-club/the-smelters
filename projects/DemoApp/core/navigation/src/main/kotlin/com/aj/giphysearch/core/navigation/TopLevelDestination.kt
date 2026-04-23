package com.aj.giphysearch.core.navigation

data class TopLevelDestination<T : Any>(
    val route: T,
    val testTag: String,
)

val topLevelDestinations = listOf(
    TopLevelDestination(
        route = SearchRoute,
        testTag = "SearchTab",
    ),
    TopLevelDestination(
        route = TrendingRoute,
        testTag = "TrendingTab",
    ),
)
