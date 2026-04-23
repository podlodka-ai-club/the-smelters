package com.aj.giphysearch.integration

import android.content.pm.ActivityInfo
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.aj.giphysearch.ui.MainActivity
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.fakes.FakeGifRepository
import com.aj.giphysearch.domain.gifs.fakes.testGifs
import com.aj.giphysearch.domain.gifs.fakes.trendingTestGifs
import com.kaspersky.components.composesupport.config.withComposeSupport
import com.kaspersky.kaspresso.kaspresso.Kaspresso
import com.kaspersky.kaspresso.testcases.api.testcase.TestCase
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.koin.test.KoinTest
import org.koin.test.inject

@RunWith(AndroidJUnit4::class)
class NavigationTest : TestCase(
    kaspressoBuilder = Kaspresso.Builder.withComposeSupport()
), KoinTest {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    private val repository: FakeGifRepository by inject()

    @Before
    fun setUp() {
        resetRepositoryState()
    }

    @Test
    fun testSearchQueryIsRestoredWhenSwitchingTabs() = run {
        step("Wait for app shell to be ready") {
            waitForAppShell()
        }

        step("Type a search query on Search tab") {
            openSearchTab()
            typeSearchQuery("cats")
        }

        step("Switch to Trending and back to Search") {
            openTrendingTab()
            openSearchTab()
        }

        step("Verify Search query is preserved") {
            assertSearchFieldContains("cats")
        }
    }

    @Test
    fun testReselectingSearchTabDoesNotResetSearchField() = run {
        step("Wait for app shell to be ready") {
            waitForAppShell()
        }

        step("Type query in Search field") {
            openSearchTab()
            composeTestRule.onNodeWithTag("SearchField").performTextClearance()
            typeSearchQuery("dogs")
        }

        step("Reselect Search tab") {
            openSearchTab()
        }

        step("Verify Search query remains after reselection") {
            assertSearchFieldContains("dogs")
        }
    }

    @Test
    fun testNavigationFromTrendingToDetailsAndBack() = run {
        step("Wait for app shell to be ready") {
            waitForAppShell()
        }

        step("Prepare data") {
            repository.trendingOutcome = GifLoadResult.Success(trendingTestGifs)
            repository.emitGifDetails(trendingTestGifs[0])
        }

        step("Check Trending Screen is displayed") {
            openTrendingTab()
            composeTestRule.onNodeWithTag("GifGrid").assertIsDisplayed()
        }

        step("Navigate to Details Screen") {
            composeTestRule.onNodeWithTag("GifItem_${trendingTestGifs[0].id}").performClick()
        }

        step("Check Details Screen is displayed") {
            composeTestRule.onNodeWithTag("GifTitle_${trendingTestGifs[0].title}")
                .assertIsDisplayed()
        }

        step("Navigate back to Trending Screen") {
            composeTestRule.onNodeWithTag("BackButton").performClick()
        }

        step("Check Trending Screen is displayed again") {
            composeTestRule.onNodeWithTag("GifGrid").assertIsDisplayed()
        }
    }

    @Test
    fun testNavigationFromSearchToDetailsAndBack() = run {
        step("Wait for app shell to be ready") {
            waitForAppShell()
        }

        step("Prepare data") {
            repository.searchOutcome = GifLoadResult.Success(testGifs)
            repository.emitGifDetails(testGifs[0])
        }

        step("Navigate to Search Screen") {
            openSearchTab()
            typeSearchQuery("test")
        }

        step("Wait for Search Results") {
            waitForGifItem(testGifs[0].id)
        }

        step("Navigate to Details Screen from Search") {
            composeTestRule.onNodeWithTag("GifItem_${testGifs[0].id}").performClick()
        }

        step("Check Details Screen is displayed") {
            composeTestRule.onNodeWithTag("GifTitle_${testGifs[0].title}").assertIsDisplayed()
        }

        step("Navigate back to Search Screen") {
            composeTestRule.onNodeWithTag("BackButton").performClick()
        }

        step("Check Search Screen is displayed again") {
            composeTestRule.onNodeWithTag("SearchField").assertIsDisplayed()
        }
    }

    @Test
    fun testSearchErrorRetryRecoversAndNavigatesToDetails() = run {
        step("Wait for app shell to be ready") {
            waitForAppShell()
        }

        step("Prepare search failure first") {
            repository.searchOutcome = GifLoadResult.Failure(GifDomainError.Unknown)
        }

        step("Trigger search and verify error state") {
            openSearchTab()
            typeSearchQuery("retry")
            composeTestRule.waitUntil(timeoutMillis = 10_000) {
                composeTestRule
                    .onAllNodesWithTag("SearchErrorState")
                    .fetchSemanticsNodes()
                    .isNotEmpty()
            }
            composeTestRule.onNodeWithTag("SearchErrorState").assertIsDisplayed()
            composeTestRule.onNodeWithTag("SearchRetryButton").assertIsDisplayed()
        }

        step("Switch repository to success and retry") {
            repository.searchOutcome = GifLoadResult.Success(testGifs)
            repository.emitGifDetails(testGifs[0])
            composeTestRule.onNodeWithTag("SearchRetryButton").performClick()
            waitForGifItem(testGifs[0].id)
        }

        step("Navigate to details and back after recovery") {
            composeTestRule.onNodeWithTag("GifItem_${testGifs[0].id}").performClick()
            composeTestRule.onNodeWithTag("GifTitle_${testGifs[0].title}").assertIsDisplayed()
            composeTestRule.onNodeWithTag("BackButton").performClick()
            composeTestRule.onNodeWithTag("SearchField").assertIsDisplayed()
        }
    }

    @Test
    fun testTrendingGridPersistsAcrossOrientationChange() = run {
        step("Wait for app shell to be ready") {
            waitForAppShell()
        }

        step("Prepare trending data and open trending tab") {
            repository.trendingOutcome = GifLoadResult.Success(trendingTestGifs)
            openTrendingTab()
            composeTestRule.onNodeWithTag("GifGrid").assertIsDisplayed()
        }

        step("Rotate to landscape and verify grid is still visible") {
            composeTestRule.activity.requestedOrientation =
                ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
            composeTestRule.waitForIdle()
            composeTestRule.onNodeWithTag("GifGrid").assertIsDisplayed()
        }

        step("Rotate back to portrait and verify grid remains visible") {
            composeTestRule.activity.requestedOrientation =
                ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
            composeTestRule.waitForIdle()
            composeTestRule.onNodeWithTag("GifGrid").assertIsDisplayed()
        }
    }

    private fun waitForAppShell() {
        composeTestRule.waitUntil(timeoutMillis = 15_000) {
            val hasSearchTab = composeTestRule
                .onAllNodesWithTag("SearchTab")
                .fetchSemanticsNodes()
                .isNotEmpty()
            val hasTrendingTab = composeTestRule
                .onAllNodesWithTag("TrendingTab")
                .fetchSemanticsNodes()
                .isNotEmpty()
            hasSearchTab && hasTrendingTab
        }
    }

    private fun openSearchTab() {
        composeTestRule.onNodeWithTag("SearchTab").performClick()
    }

    private fun openTrendingTab() {
        composeTestRule.onNodeWithTag("TrendingTab").performClick()
    }

    private fun typeSearchQuery(query: String) {
        composeTestRule.onNodeWithTag("SearchField").performTextClearance()
        composeTestRule.onNodeWithTag("SearchField").performTextInput(query)
    }

    private fun assertSearchFieldContains(query: String) {
        composeTestRule.onNodeWithTag("SearchField").assertTextContains(query)
    }

    private fun waitForGifItem(gifId: String) {
        composeTestRule.waitUntil(timeoutMillis = 10_000) {
            composeTestRule
                .onAllNodesWithTag("GifItem_$gifId")
                .fetchSemanticsNodes()
                .isNotEmpty()
        }
    }

    private fun resetRepositoryState() {
        repository.searchOutcome = GifLoadResult.Success(emptyList())
        repository.trendingOutcome = GifLoadResult.Success(emptyList())
        repository.gifByIdOutcome = GifLoadResult.Failure(GifDomainError.Unknown)
        repository.searchDelayMs = 0L
        repository.trendingDelayMs = 0L
        repository.gifByIdDelayMs = 0L
    }
}
