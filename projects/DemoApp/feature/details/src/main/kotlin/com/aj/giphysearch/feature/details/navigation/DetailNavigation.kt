package com.aj.giphysearch.feature.details.navigation

import androidx.navigation.NavGraphBuilder
import androidx.navigation.compose.composable
import androidx.navigation.toRoute
import com.aj.giphysearch.core.navigation.DetailRoute
import com.aj.giphysearch.feature.details.ui.DetailScreen

fun NavGraphBuilder.detailDestination(
    onBack: () -> Unit,
) {
    composable<DetailRoute> { backStackEntry ->
        val route = backStackEntry.toRoute<DetailRoute>()
        DetailScreen(
            gifId = route.gifId,
            onBack = onBack,
        )
    }
}
