package com.aj.giphysearch

import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.kaspersky.components.composesupport.config.withComposeSupport
import com.kaspersky.kaspresso.kaspresso.Kaspresso
import com.kaspersky.kaspresso.testcases.api.testcase.TestCase
import com.aj.giphysearch.screens.DetailScreenObject
import com.aj.giphysearch.screens.SearchScreenObject
import com.aj.giphysearch.screens.TrendingScreenObject
import io.github.kakaocup.compose.node.element.ComposeScreen
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Navigation integration tests covering the full app flow.
 *
 * Covered scenarios:
 *  - Tapping a GIF on the Search screen opens the Detail screen
 *  - Back button on the Detail screen returns to the previous grid
 *  - Bottom navigation switches between Search and Trending tabs
 *  - Tapping a GIF on the Trending screen opens the Detail screen
 */
@RunWith(AndroidJUnit4::class)
class NavigationTest : TestCase(
    kaspressoBuilder = Kaspresso.Builder.withComposeSupport(),
) {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun tappingGif_onSearchScreen_navigatesToDetail() = run {
        step("Type a valid query to load GIFs") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchField.performTextInput("Te")
            }
        }
        step("Wait for GIF items to appear") {
            composeTestRule.waitUntil(timeoutMillis = 5_000) {
                composeTestRule.onAllNodesWithTag("gif_item")
                    .fetchSemanticsNodes().isNotEmpty()
            }
        }
        step("Tap the first GIF item") {
            composeTestRule.onAllNodesWithTag("gif_item").onFirst().performClick()
        }
        step("Verify the Detail screen is shown") {
            ComposeScreen.onComposeScreen<DetailScreenObject>(composeTestRule) {
                assertIsDisplayed()
            }
        }
    }

    @Test
    fun backButton_onDetailScreen_returnsToGrid() = run {
        step("Navigate to Trending and tap the first GIF") {
            composeTestRule.onNodeWithText("Trending").performClick()
            composeTestRule.waitUntil(timeoutMillis = 5_000) {
                composeTestRule.onAllNodesWithTag("gif_item")
                    .fetchSemanticsNodes().isNotEmpty()
            }
            composeTestRule.onAllNodesWithTag("gif_item").onFirst().performClick()
        }
        step("Verify the Detail screen is shown") {
            ComposeScreen.onComposeScreen<DetailScreenObject>(composeTestRule) {
                assertIsDisplayed()
            }
        }
        step("Press the back button") {
            ComposeScreen.onComposeScreen<DetailScreenObject>(composeTestRule) {
                backButton.performClick()
            }
        }
        step("Verify the GIF grid is visible again") {
            ComposeScreen.onComposeScreen<TrendingScreenObject>(composeTestRule) {
                gifGrid.assertIsDisplayed()
            }
        }
    }

    @Test
    fun bottomNav_switchesBetweenSearchAndTrending() = run {
        step("App opens on the Search screen") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                assertIsDisplayed()
            }
        }
        step("Tap the Trending tab") {
            composeTestRule.onNodeWithText("Trending").performClick()
        }
        step("Verify the Trending screen is shown") {
            ComposeScreen.onComposeScreen<TrendingScreenObject>(composeTestRule) {
                assertIsDisplayed()
            }
        }
        step("Tap the Search tab to go back") {
            composeTestRule.onNodeWithText("Search").performClick()
        }
        step("Verify the Search screen is shown again") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                assertIsDisplayed()
            }
        }
    }

    @Test
    fun tappingGif_onTrendingScreen_navigatesToDetail() = run {
        step("Navigate to Trending and wait for GIFs") {
            composeTestRule.onNodeWithText("Trending").performClick()
            composeTestRule.waitUntil(timeoutMillis = 5_000) {
                composeTestRule.onAllNodesWithTag("gif_item")
                    .fetchSemanticsNodes().isNotEmpty()
            }
        }
        step("Tap the first GIF") {
            composeTestRule.onAllNodesWithTag("gif_item").onFirst().performClick()
        }
        step("Verify Detail screen is shown") {
            ComposeScreen.onComposeScreen<DetailScreenObject>(composeTestRule) {
                assertIsDisplayed()
            }
        }
    }
}
