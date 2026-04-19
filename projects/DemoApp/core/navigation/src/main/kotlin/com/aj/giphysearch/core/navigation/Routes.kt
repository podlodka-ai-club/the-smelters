package com.aj.giphysearch.core.navigation

import kotlinx.serialization.Serializable

@Serializable
data object SearchRoute

@Serializable
data object TrendingRoute

@Serializable
data class DetailRoute(val gifId: String)
