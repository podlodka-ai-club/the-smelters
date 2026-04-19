package com.aj.giphysearch

import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.kaspersky.components.composesupport.config.withComposeSupport
import com.kaspersky.kaspresso.kaspresso.Kaspresso
import com.kaspersky.kaspresso.testcases.api.testcase.TestCase
import com.aj.giphysearch.screens.SearchScreenObject
import io.github.kakaocup.compose.node.element.ComposeScreen
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * UI tests for [SearchScreen].
 *
 * Covered scenarios:
 *  - Search field is visible on launch
 *  - Prompt shown when query is too short (< 2 chars)
 *  - GIF grid appears after a valid query (debounce)
 *  - Clear button wipes the search field
 */
@RunWith(AndroidJUnit4::class)
class SearchScreenTest : TestCase(
    kaspressoBuilder = Kaspresso.Builder.withComposeSupport(),
) {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun searchField_isDisplayed_onLaunch() = run {
        step("Verify search field is visible on the initial screen") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchField.assertIsDisplayed()
            }
        }
    }

    @Test
    fun searchPrompt_isShown_whenQueryIsEmpty() = run {
        step("Verify search prompt is visible when nothing has been typed") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchPrompt.assertIsDisplayed()
            }
        }
    }

    @Test
    fun searchPrompt_isShown_whenQueryIsTooShort() = run {
        step("Type a single character into the search field") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchField.performTextInput("a")
            }
        }
        step("Verify the prompt is still shown — query is only 1 char") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchPrompt.assertIsDisplayed()
            }
        }
    }

    @Test
    fun gifGrid_appearsAfterValidQuery() = run {
        step("Type a valid search query (2+ chars)") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchField.performTextInput("Te")
            }
        }
        step("Wait for debounce + paging to produce GIF items") {
            composeTestRule.waitUntil(timeoutMillis = 5_000) {
                composeTestRule
                    .onAllNodesWithTag("gif_item")
                    .fetchSemanticsNodes()
                    .isNotEmpty()
            }
        }
        step("Verify the GIF grid is displayed with results") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                gifGrid.assertIsDisplayed()
            }
        }
    }

    @Test
    fun clearButton_clearsSearchField() = run {
        step("Type a query so the clear button appears") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchField.performTextInput("cats")
            }
        }
        step("Tap the clear (X) button") {
            composeTestRule
                .onAllNodesWithContentDescription("Clear")
                .onFirst()
                .performClick()
        }
        step("Verify the search prompt is back — field was cleared") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchPrompt.assertIsDisplayed()
            }
        }
    }
}
