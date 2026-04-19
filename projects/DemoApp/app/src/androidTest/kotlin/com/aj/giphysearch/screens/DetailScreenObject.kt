package com.aj.giphysearch.screens

import androidx.compose.ui.test.SemanticsNodeInteractionsProvider
import io.github.kakaocup.compose.node.element.ComposeScreen
import io.github.kakaocup.compose.node.element.KNode

class DetailScreenObject(semanticsProvider: SemanticsNodeInteractionsProvider) :
    ComposeScreen<DetailScreenObject>(
        semanticsProvider = semanticsProvider,
        viewBuilderAction = { hasTestTag("detail_screen") },
    ) {

    val backButton: KNode = child { hasContentDescription("Back") }
}
