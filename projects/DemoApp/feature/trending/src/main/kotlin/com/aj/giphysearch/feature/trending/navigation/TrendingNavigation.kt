package com.aj.giphysearch.feature.trending.navigation

import androidx.compose.foundation.layout.PaddingValues
import androidx.navigation.NavGraphBuilder
import androidx.navigation.compose.composable
import com.aj.giphysearch.core.navigation.TrendingRoute
import com.aj.giphysearch.feature.trending.ui.TrendingScreen

fun NavGraphBuilder.trendingDestination(
    contentPadding: PaddingValues,
    onGifClick: (String) -> Unit,
) {
    composable<TrendingRoute> {
        TrendingScreen(
            onGifClick = onGifClick,
            contentPadding = contentPadding,
        )
    }
}
