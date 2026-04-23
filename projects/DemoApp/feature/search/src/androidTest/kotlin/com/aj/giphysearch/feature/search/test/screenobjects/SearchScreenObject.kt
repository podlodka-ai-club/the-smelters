package com.aj.giphysearch.feature.search.test.screenobjects

import androidx.compose.ui.test.SemanticsNodeInteractionsProvider
import io.github.kakaocup.compose.node.element.ComposeScreen
import io.github.kakaocup.compose.node.element.KNode

class SearchScreenObject(
    semanticsProvider: SemanticsNodeInteractionsProvider
) : ComposeScreen<SearchScreenObject>(
    semanticsProvider = semanticsProvider,
    viewBuilderAction = { hasTestTag("SearchScreen") }
) {
    val searchField: KNode = child {
        hasTestTag("SearchField")
    }
    val clearButton: KNode = child {
        hasTestTag("SearchClearButton")
    }
    val searchPrompt: KNode = child {
        hasTestTag("SearchPrompt")
    }
    val gifGrid: KNode = child {
        hasTestTag("GifGrid")
    }
    val loading: KNode = child {
        hasTestTag("SearchLoading")
    }
    val errorState: KNode = child {
        hasTestTag("SearchErrorState")
    }
    val retryButton: KNode = child {
        hasTestTag("SearchRetryButton")
    }
    val emptyState: KNode = child {
        hasTestTag("SearchEmptyState")
    }

    fun gifItem(id: String): KNode = child {
        hasTestTag("GifItem_$id")
    }
}
