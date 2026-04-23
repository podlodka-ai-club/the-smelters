package com.aj.giphysearch.core.navigation

import kotlinx.serialization.Serializable

@Serializable
object SearchRoute

@Serializable
object TrendingRoute

@Serializable
data class DetailRoute(val gifId: String)
