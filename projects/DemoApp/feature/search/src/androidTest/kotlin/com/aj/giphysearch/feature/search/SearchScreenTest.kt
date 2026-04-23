package com.aj.giphysearch.feature.search

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.aj.giphysearch.core.ui.test.KoinTestRule
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.fakes.FakeGifRepository
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.usecase.SearchGifsUseCase
import com.aj.giphysearch.feature.search.test.screenobjects.SearchScreenObject
import com.aj.giphysearch.feature.search.ui.SearchScreen
import com.aj.giphysearch.feature.search.ui.SearchViewModel
import com.kaspersky.components.composesupport.config.withComposeSupport
import com.kaspersky.kaspresso.kaspresso.Kaspresso
import com.kaspersky.kaspresso.testcases.api.testcase.TestCase
import io.github.kakaocup.compose.node.element.ComposeScreen
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.koin.dsl.module

/**
 * UI tests for [com.aj.giphysearch.feature.search.ui.SearchScreen].
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

    private val fakeRepo = FakeGifRepository()

    @get:Rule(order = 0)
    val koinTestRule = KoinTestRule(
        modules = listOf(
            module {
                single { SearchGifsUseCase(fakeRepo) }
                factory { SearchViewModel(get()) }
            }
        )
    )

    @get:Rule(order = 1)
    val composeTestRule = createAndroidComposeRule<ComponentActivity>()

    @Before
    fun setup() {
        fakeRepo.searchOutcome = GifLoadResult.Success(
            listOf(Gif("1", "test", "url", "url", "url", "url", "url", 100, 100)),
        )
        fakeRepo.searchDelayMs = 0L

        composeTestRule.setContent {
            SearchScreen(
                onGifClick = {}
            )
        }
    }

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
                    .onAllNodesWithTag("GifItem_1")
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
        step("Tap the clear (X) button from test tag") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                clearButton.performClick()
            }
        }
        step("Verify the search prompt is back — field was cleared") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchPrompt.assertIsDisplayed()
            }
        }
    }

    @Test
    fun loadingState_isShown_whileSearchIsInFlight() = run {
        step("Configure delayed success response") {
            fakeRepo.searchDelayMs = 1_500L
            fakeRepo.searchOutcome = GifLoadResult.Success(
                listOf(Gif("1", "test", "url", "url", "url", "url", "url", 100, 100)),
            )
        }
        step("Type a valid query") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchField.performTextInput("loading")
            }
        }
        step("Verify loading indicator appears during refresh") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                loading.assertIsDisplayed()
            }
        }
    }

    @Test
    fun emptyState_isShown_whenSearchReturnsNoResults() = run {
        step("Configure empty successful search response") {
            fakeRepo.searchOutcome = GifLoadResult.Success(emptyList())
        }
        step("Search with a valid query") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchField.performTextInput("empty")
            }
        }
        step("Verify empty state is shown") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                emptyState.assertIsDisplayed()
            }
        }
    }

    @Test
    fun retry_recoversFromError_andDisplaysGrid() = run {
        step("Start with a failed search response") {
            fakeRepo.searchOutcome = GifLoadResult.Failure(GifDomainError.Unknown)
        }
        step("Search and verify error state appears") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                searchField.performTextInput("fail")
                errorState.assertIsDisplayed()
                retryButton.assertIsDisplayed()
            }
        }
        step("Switch repository response to success") {
            fakeRepo.searchOutcome = GifLoadResult.Success(
                listOf(Gif("1", "test", "url", "url", "url", "url", "url", 100, 100)),
            )
        }
        step("Tap retry and wait for item to appear") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                retryButton.performClick()
            }
            composeTestRule.waitUntil(timeoutMillis = 5_000) {
                composeTestRule
                    .onAllNodesWithTag("GifItem_1")
                    .fetchSemanticsNodes()
                    .isNotEmpty()
            }
        }
        step("Verify GIF grid is displayed again") {
            ComposeScreen.onComposeScreen<SearchScreenObject>(composeTestRule) {
                gifGrid.assertIsDisplayed()
            }
        }
    }
}