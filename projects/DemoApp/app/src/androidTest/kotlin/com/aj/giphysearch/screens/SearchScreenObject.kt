package com.aj.giphysearch.screens

import androidx.compose.ui.test.SemanticsNodeInteractionsProvider
import io.github.kakaocup.compose.node.element.ComposeScreen
import io.github.kakaocup.compose.node.element.KNode

class SearchScreenObject(semanticsProvider: SemanticsNodeInteractionsProvider) :
    ComposeScreen<SearchScreenObject>(
        semanticsProvider = semanticsProvider,
        viewBuilderAction = { hasTestTag("search_screen") },
    ) {

    val searchField: KNode = child { hasTestTag("search_field") }
    val searchPrompt: KNode = child { hasTestTag("search_prompt") }
    val gifGrid: KNode = child { hasTestTag("gif_grid") }
}
