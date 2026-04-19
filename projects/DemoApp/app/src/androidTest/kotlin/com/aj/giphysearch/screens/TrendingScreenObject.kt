package com.aj.giphysearch.screens

import androidx.compose.ui.test.SemanticsNodeInteractionsProvider
import io.github.kakaocup.compose.node.element.ComposeScreen
import io.github.kakaocup.compose.node.element.KNode

class TrendingScreenObject(semanticsProvider: SemanticsNodeInteractionsProvider) :
    ComposeScreen<TrendingScreenObject>(
        semanticsProvider = semanticsProvider,
        viewBuilderAction = { hasTestTag("trending_screen") },
    ) {

    val gifGrid: KNode = child { hasTestTag("gif_grid") }
    val gifItems: KNode = child { hasTestTag("gif_item") }
}
