package com.aj.giphysearch

import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.kaspersky.components.composesupport.config.withComposeSupport
import com.kaspersky.kaspresso.kaspresso.Kaspresso
import com.kaspersky.kaspresso.testcases.api.testcase.TestCase
import com.aj.giphysearch.screens.SearchScreenObject
import com.aj.giphysearch.screens.TrendingScreenObject
import io.github.kakaocup.compose.node.element.ComposeScreen
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * UI tests for [TrendingScreen].
 *
 * Covered scenarios:
 *  - Trending tab is reachable from the bottom navigation bar
 *  - GIF grid loads and displays items on the Trending screen
 */
@RunWith(AndroidJUnit4::class)
class TrendingScreenTest : TestCase(
    kaspressoBuilder = Kaspresso.Builder.withComposeSupport(),
) {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun trendingTab_isAccessibleFromBottomNav() = run {
        step("Tap the Trending tab in the bottom navigation bar") {
            composeTestRule.onNodeWithText("Trending").performClick()
        }
        step("Verify the Trending screen root is shown") {
            ComposeScreen.onComposeScreen<TrendingScreenObject>(composeTestRule) {
                assertIsDisplayed()
            }
        }
    }

    @Test
    fun gifGrid_loadsOnTrendingScreen() = run {
        step("Navigate to the Trending tab") {
            composeTestRule.onNodeWithText("Trending").performClick()
        }
        step("Wait for GIF items to appear in the grid") {
            composeTestRule.waitUntil(timeoutMillis = 5_000) {
                composeTestRule
                    .onAllNodesWithTag("gif_item")
                    .fetchSemanticsNodes()
                    .isNotEmpty()
            }
        }
        step("Verify the GIF grid is displayed") {
            ComposeScreen.onComposeScreen<TrendingScreenObject>(composeTestRule) {
                gifGrid.assertIsDisplayed()
            }
        }
    }
}
