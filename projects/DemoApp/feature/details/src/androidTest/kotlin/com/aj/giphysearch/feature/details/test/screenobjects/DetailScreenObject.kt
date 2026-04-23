package com.aj.giphysearch.feature.details.test.screenobjects

import androidx.compose.ui.test.SemanticsNodeInteractionsProvider
import io.github.kakaocup.compose.node.element.ComposeScreen
import io.github.kakaocup.compose.node.element.KNode

class DetailScreenObject(
    semanticsProvider: SemanticsNodeInteractionsProvider
) : ComposeScreen<DetailScreenObject>(
    semanticsProvider = semanticsProvider,
    viewBuilderAction = { hasTestTag("DetailScreen") }
) {
    val backButton: KNode = child {
        hasTestTag("BackButton")
    }
    val loading: KNode = child {
        hasTestTag("DetailLoading")
    }
    val errorState: KNode = child {
        hasTestTag("DetailErrorState")
    }
    val retryButton: KNode = child {
        hasTestTag("DetailRetryButton")
    }

    fun gifTitle(title: String): KNode = child {
        hasTestTag("GifTitle_$title")
    }
}
