package com.aj.giphysearch.feature.details

import app.cash.turbine.test
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.fakes.FakeGifRepository
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.usecase.GetGifByIdUseCase
import com.aj.giphysearch.feature.details.ui.DetailViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DetailViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var repository: FakeGifRepository

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        repository = FakeGifRepository()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `loads gif successfully when state is collected`() = runTest {
        val gif = fakeGif("42")
        repository.gifByIdOutcome = GifLoadResult.Success(gif)
        val viewModel = DetailViewModel(GetGifByIdUseCase(repository), "42")

        viewModel.uiState.test {
            val loading = awaitItem()
            assertTrue(loading.isLoading)
            testDispatcher.scheduler.advanceUntilIdle()
            val loaded = awaitItem()
            assertFalse(loaded.isLoading)
            assertNull(loaded.error)
            assertNotNull(loaded.gif)
            assertEquals("42", loaded.gif?.id)
            cancelAndConsumeRemainingEvents()
        }
    }

    @Test
    fun `shows error on failure`() = runTest {
        repository.gifByIdOutcome = GifLoadResult.Failure(GifDomainError.Unknown)
        val viewModel = DetailViewModel(GetGifByIdUseCase(repository), "99")

        viewModel.uiState.test {
            val loading = awaitItem()
            assertTrue(loading.isLoading)
            testDispatcher.scheduler.advanceUntilIdle()
            val error = awaitItem()
            assertFalse(error.isLoading)
            assertNotNull(error.error)
            assertNull(error.gif)
            cancelAndConsumeRemainingEvents()
        }
    }

    @Test
    fun `retry reloads gif after error`() = runTest {
        repository.gifByIdOutcome = GifLoadResult.Failure(GifDomainError.Unknown)
        val viewModel = DetailViewModel(GetGifByIdUseCase(repository), "1")

        viewModel.uiState.test {
            awaitItem() // loading
            testDispatcher.scheduler.advanceUntilIdle()
            val firstError = awaitItem()
            assertFalse(firstError.isLoading)
            assertNotNull(firstError.error)

            repository.gifByIdOutcome = GifLoadResult.Success(fakeGif("1"))
            viewModel.retry()
            testDispatcher.scheduler.advanceUntilIdle()

            val retriedLoading = awaitItem()
            assertTrue(retriedLoading.isLoading)
            val retriedSuccess = awaitItem()
            assertFalse(retriedSuccess.isLoading)
            assertNull(retriedSuccess.error)
            assertEquals("1", retriedSuccess.gif?.id)
            cancelAndConsumeRemainingEvents()
        }
    }

    private fun fakeGif(id: String) = Gif(
        id = id,
        title = "Test GIF",
        rating = "g",
        username = "tester",
        source = "https://example.com",
        originalUrl = "https://example.com/original.gif",
        previewUrl = "https://example.com/preview.gif",
        width = 100,
        height = 100
    )
}
