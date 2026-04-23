package com.aj.giphysearch.feature.trending.test.screenobjects

import androidx.compose.ui.test.SemanticsNodeInteractionsProvider
import io.github.kakaocup.compose.node.element.ComposeScreen
import io.github.kakaocup.compose.node.element.KNode

class TrendingScreenObject(
    semanticsProvider: SemanticsNodeInteractionsProvider
) : ComposeScreen<TrendingScreenObject>(
    semanticsProvider = semanticsProvider,
    viewBuilderAction = { hasTestTag("TrendingScreen") }
) {
    val gifGrid: KNode = child {
        hasTestTag("GifGrid")
    }
    val loading: KNode = child {
        hasTestTag("TrendingLoading")
    }
    val errorState: KNode = child {
        hasTestTag("TrendingErrorState")
    }
    val retryButton: KNode = child {
        hasTestTag("TrendingRetryButton")
    }

    fun gifItem(id: String): KNode = child {
        hasTestTag("GifItem_$id")
    }
}
