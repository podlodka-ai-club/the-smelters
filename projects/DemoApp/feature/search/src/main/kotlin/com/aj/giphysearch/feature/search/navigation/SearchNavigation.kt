package com.aj.giphysearch.feature.search.navigation

import androidx.compose.foundation.layout.PaddingValues
import androidx.navigation.NavGraphBuilder
import androidx.navigation.compose.composable
import com.aj.giphysearch.core.navigation.SearchRoute
import com.aj.giphysearch.feature.search.ui.SearchScreen

fun NavGraphBuilder.searchDestination(
    contentPadding: PaddingValues,
    onGifClick: (String) -> Unit,
) {
    composable<SearchRoute> {
        SearchScreen(
            onGifClick = onGifClick,
            contentPadding = contentPadding,
        )
    }
}
