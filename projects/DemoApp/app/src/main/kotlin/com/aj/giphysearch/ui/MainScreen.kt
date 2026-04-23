package com.aj.giphysearch.ui

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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.aj.giphysearch.R
import com.aj.giphysearch.core.navigation.SearchRoute
import com.aj.giphysearch.core.navigation.TopLevelDestination
import com.aj.giphysearch.core.navigation.TrendingRoute
import com.aj.giphysearch.core.navigation.topLevelDestinations
import com.aj.giphysearch.navigation.AppNavHost

@Composable
fun MainScreen() {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    val showBottomBar = currentDestination?.let { destination ->
        topLevelDestinations.any { topLevel -> destination.hasRoute(topLevel.route::class) }
    } ?: true

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    topLevelDestinations.forEach { destination ->
                        NavigationBarItem(
                            modifier = Modifier.testTag(destination.testTag),
                            selected = currentDestination?.hasRoute(destination.route::class) == true,
                            onClick = {
                                navController.navigate(destination.route) {
                                    launchSingleTop = true
                                    restoreState = true
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                }
                            },
                            icon = {
                                Icon(
                                    imageVector = destination.icon(),
                                    contentDescription = stringResource(destination.labelRes()),
                                )
                            },
                            label = { Text(stringResource(destination.labelRes())) },
                        )
                    }
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

private fun TopLevelDestination<*>.icon() = when (route) {
    SearchRoute -> Icons.Default.Search
    TrendingRoute -> Icons.Default.Star
    else -> Icons.Default.Search
}

private fun TopLevelDestination<*>.labelRes() = when (route) {
    SearchRoute -> R.string.search
    TrendingRoute -> R.string.trending
    else -> R.string.search
}
