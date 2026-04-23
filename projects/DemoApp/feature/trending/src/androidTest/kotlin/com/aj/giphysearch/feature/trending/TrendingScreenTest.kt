package com.aj.giphysearch.feature.trending

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.aj.giphysearch.core.ui.test.KoinTestRule
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.fakes.FakeGifRepository
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.usecase.GetTrendingGifsUseCase
import com.aj.giphysearch.feature.trending.test.screenobjects.TrendingScreenObject
import com.aj.giphysearch.feature.trending.ui.TrendingScreen
import com.aj.giphysearch.feature.trending.ui.TrendingViewModel
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
 * UI tests for [com.aj.giphysearch.feature.trending.ui.TrendingScreen].
 *
 * Covered scenarios:
 *  - GIF grid loads and displays items on the Trending screen
 */
@RunWith(AndroidJUnit4::class)
class TrendingScreenTest : TestCase(
    kaspressoBuilder = Kaspresso.Builder.withComposeSupport(),
) {

    private val fakeRepo = FakeGifRepository()

    @get:Rule(order = 0)
    val koinTestRule = KoinTestRule(
        modules = listOf(
            module {
                single { GetTrendingGifsUseCase(fakeRepo) }
                factory { TrendingViewModel(get()) }
            }
        )
    )

    @get:Rule(order = 1)
    val composeTestRule = createAndroidComposeRule<ComponentActivity>()

    @Before
    fun setup() {
        resetRepository()
    }

    private fun resetRepository() {
        fakeRepo.trendingOutcome = GifLoadResult.Success(
            listOf(Gif("1", "test", "url", "url", "url", "url", "url", 100, 100)),
        )
        fakeRepo.trendingDelayMs = 0L
    }

    private fun setContent() {
        composeTestRule.setContent {
            TrendingScreen(
                onGifClick = {}
            )
        }
    }

    @Test
    fun gifGrid_loadsOnTrendingScreen() = run {
        step("Render Trending screen") {
            setContent()
        }
        step("Wait for GIF items to appear in the grid") {
            composeTestRule.waitUntil(timeoutMillis = 5_000) {
                composeTestRule
                    .onAllNodesWithTag("GifItem_1")
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

    @Test
    fun loadingState_isShown_whileTrendingRequestIsRunning() = run {
        step("Configure delayed success response") {
            fakeRepo.trendingDelayMs = 5_000L
        }
        step("Render Trending screen") {
            setContent()
        }
        step("Verify loading indicator appears") {
            ComposeScreen.onComposeScreen<TrendingScreenObject>(composeTestRule) {
                loading.assertIsDisplayed()
            }
        }
    }

    @Test
    fun retry_recoversFromError_andDisplaysGrid() = run {
        step("Set first response to failure and render screen") {
            fakeRepo.trendingOutcome = GifLoadResult.Failure(GifDomainError.Unknown)
            setContent()
        }
        step("Verify error state and retry button are visible") {
            ComposeScreen.onComposeScreen<TrendingScreenObject>(composeTestRule) {
                errorState.assertIsDisplayed()
                retryButton.assertIsDisplayed()
            }
        }
        step("Switch repository response to success") {
            fakeRepo.trendingOutcome = GifLoadResult.Success(
                listOf(Gif("1", "test", "url", "url", "url", "url", "url", 100, 100)),
            )
        }
        step("Tap retry and wait for first GIF item") {
            ComposeScreen.onComposeScreen<TrendingScreenObject>(composeTestRule) {
                retryButton.performClick()
            }
            composeTestRule.waitUntil(timeoutMillis = 5_000) {
                composeTestRule
                    .onAllNodesWithTag("GifItem_1")
                    .fetchSemanticsNodes()
                    .isNotEmpty()
            }
        }
        step("Verify grid is displayed after recovery") {
            ComposeScreen.onComposeScreen<TrendingScreenObject>(composeTestRule) {
                gifGrid.assertIsDisplayed()
            }
        }
    }
}