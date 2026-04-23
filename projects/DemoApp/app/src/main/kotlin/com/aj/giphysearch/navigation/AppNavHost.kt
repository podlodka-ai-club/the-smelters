package com.aj.giphysearch.navigation

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import com.aj.giphysearch.core.navigation.DetailRoute
import com.aj.giphysearch.core.navigation.SearchRoute
import com.aj.giphysearch.feature.details.navigation.detailDestination
import com.aj.giphysearch.feature.search.navigation.searchDestination
import com.aj.giphysearch.feature.trending.navigation.trendingDestination

@Composable
fun AppNavHost(
    navController: NavHostController,
    contentPadding: PaddingValues = PaddingValues(0.dp),
) {
    NavHost(
        navController = navController,
        startDestination = SearchRoute,
        modifier = Modifier.fillMaxSize(),
    ) {
        searchDestination(
            contentPadding = contentPadding,
            onGifClick = { gifId -> navController.navigate(DetailRoute(gifId)) },
        )
        trendingDestination(
            contentPadding = contentPadding,
            onGifClick = { gifId -> navController.navigate(DetailRoute(gifId)) },
        )
        detailDestination(
            onBack = { navController.popBackStack() },
        )
    }
}
