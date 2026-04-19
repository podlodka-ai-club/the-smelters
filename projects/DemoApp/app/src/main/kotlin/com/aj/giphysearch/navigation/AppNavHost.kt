package com.aj.giphysearch.navigation

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.toRoute
import com.aj.giphysearch.R
import com.aj.giphysearch.feature.details.DetailScreen
import com.aj.giphysearch.feature.search.SearchScreen
import com.aj.giphysearch.feature.trending.TrendingScreen
import kotlinx.serialization.Serializable

@Serializable
data object SearchRoute

@Serializable
data object TrendingRoute

@Serializable
data class DetailRoute(val gifId: String)

@Composable
fun MainScreen() {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    val showBottomBar = currentDestination?.let {
        it.hasRoute<SearchRoute>() || it.hasRoute<TrendingRoute>()
    } ?: true

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    NavigationBarItem(
                        selected = currentDestination?.hasRoute<SearchRoute>() == true,
                        onClick = {
                            navController.navigate(SearchRoute) {
                                launchSingleTop = true
                                popUpTo(SearchRoute) { inclusive = false }
                            }
                        },
                        icon = {
                            Icon(
                                imageVector = Icons.Default.Search,
                                contentDescription = stringResource(R.string.search),
                            )
                        },
                        label = { Text(stringResource(R.string.search)) },
                    )
                    NavigationBarItem(
                        selected = currentDestination?.hasRoute<TrendingRoute>() == true,
                        onClick = {
                            navController.navigate(TrendingRoute) {
                                launchSingleTop = true
                                popUpTo(SearchRoute) { inclusive = false }
                            }
                        },
                        icon = {
                            Icon(
                                imageVector = Icons.Default.Star,
                                contentDescription = stringResource(R.string.trending),
                            )
                        },
                        label = { Text(stringResource(R.string.trending)) },
                    )
                }
            }
        },
    ) { paddingValues ->
        AppNavHost(
            navController = navController,
            contentPadding = paddingValues,
        )
    }
}

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
        composable<SearchRoute> {
            SearchScreen(
                onGifClick = { gifId -> navController.navigate(DetailRoute(gifId)) },
                contentPadding = contentPadding,
            )
        }
        composable<TrendingRoute> {
            TrendingScreen(
                onGifClick = { gifId -> navController.navigate(DetailRoute(gifId)) },
                contentPadding = contentPadding,
            )
        }
        composable<DetailRoute> { backStackEntry ->
            val route = backStackEntry.toRoute<DetailRoute>()
            DetailScreen(
                gifId = route.gifId,
                onBack = { navController.popBackStack() },
            )
        }
    }
}
