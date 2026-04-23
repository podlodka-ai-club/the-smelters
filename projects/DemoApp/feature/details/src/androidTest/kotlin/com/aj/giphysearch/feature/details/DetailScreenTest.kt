package com.aj.giphysearch.feature.details

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.aj.giphysearch.core.ui.test.KoinTestRule
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.fakes.FakeGifRepository
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.usecase.GetGifByIdUseCase
import com.aj.giphysearch.feature.details.test.screenobjects.DetailScreenObject
import com.aj.giphysearch.feature.details.ui.DetailScreen
import com.aj.giphysearch.feature.details.ui.DetailViewModel
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
 * UI tests for [com.aj.giphysearch.feature.details.ui.DetailScreen].
 */
@RunWith(AndroidJUnit4::class)
class DetailScreenTest : TestCase(
    kaspressoBuilder = Kaspresso.Builder.withComposeSupport(),
) {

    private val fakeRepo = FakeGifRepository()

    @get:Rule(order = 0)
    val koinTestRule = KoinTestRule(
        modules = listOf(
            module {
                single { GetGifByIdUseCase(fakeRepo) }
                factory { (gifId: String) -> DetailViewModel(get(), gifId) }
            }
        )
    )

    @get:Rule(order = 1)
    val composeTestRule = createAndroidComposeRule<ComponentActivity>()

    private val testGif = Gif(
        id = "1",
        title = "Test GIF",
        rating = "g",
        username = "testuser",
        source = "url",
        originalUrl = "url",
        previewUrl = "url",
        width = 100,
        height = 100
    )

    @Before
    fun setup() {
        resetRepository()
    }

    private fun resetRepository() {
        fakeRepo.gifByIdOutcome = GifLoadResult.Success(testGif)
        fakeRepo.gifByIdDelayMs = 0L
    }

    private fun setContent() {
        composeTestRule.setContent {
            DetailScreen(
                gifId = "1",
                onBack = {}
            )
        }
    }

    @Test
    fun detailScreen_isDisplayed() = run {
        step("Render Detail screen") {
            setContent()
        }
        step("Verify Detail screen is visible") {
            ComposeScreen.onComposeScreen<DetailScreenObject>(composeTestRule) {
                assertIsDisplayed()
            }
        }
    }

    @Test
    fun loadingState_isShown_whileDetailRequestIsRunning() = run {
        step("Configure delayed response") {
            fakeRepo.gifByIdDelayMs = 5_000L
        }
        step("Render Detail screen") {
            setContent()
        }
        step("Verify loading state is visible") {
            ComposeScreen.onComposeScreen<DetailScreenObject>(composeTestRule) {
                loading.assertIsDisplayed()
            }
        }
    }

    @Test
    fun retry_recoversFromError_andShowsGifTitle() = run {
        step("Set first response to failure and render screen") {
            fakeRepo.gifByIdOutcome = GifLoadResult.Failure(GifDomainError.Unknown)
            setContent()
        }
        step("Verify error state with retry button") {
            ComposeScreen.onComposeScreen<DetailScreenObject>(composeTestRule) {
                errorState.assertIsDisplayed()
                retryButton.assertIsDisplayed()
            }
        }
        step("Switch response to success and retry") {
            fakeRepo.gifByIdOutcome = GifLoadResult.Success(testGif)
            ComposeScreen.onComposeScreen<DetailScreenObject>(composeTestRule) {
                retryButton.performClick()
            }
        }
        step("Verify title is shown after successful retry") {
            ComposeScreen.onComposeScreen<DetailScreenObject>(composeTestRule) {
                gifTitle(testGif.title).assertIsDisplayed()
            }
        }
    }
}
