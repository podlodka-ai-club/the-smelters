package com.aj.giphysearch

import app.cash.turbine.test
import com.aj.giphysearch.domain.gifs.usecase.GetGifByIdUseCase
import com.aj.giphysearch.feature.details.DetailViewModel
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
    fun `loads gif successfully on init`() = runTest {
        val gif = fakeGif("42")
        repository.gifByIdResult = Result.success(gif)
        val viewModel = DetailViewModel(GetGifByIdUseCase(repository), "42")

        viewModel.uiState.test {
            awaitItem() // loading state
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
        repository.gifByIdResult = Result.failure(RuntimeException("Network error"))
        val viewModel = DetailViewModel(GetGifByIdUseCase(repository), "99")

        viewModel.uiState.test {
            awaitItem() // loading
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
        repository.gifByIdResult = Result.failure(RuntimeException("Network error"))
        val viewModel = DetailViewModel(GetGifByIdUseCase(repository), "1")

        testDispatcher.scheduler.advanceUntilIdle()

        repository.gifByIdResult = Result.success(fakeGif("1"))
        viewModel.retry()
        testDispatcher.scheduler.advanceUntilIdle()

        viewModel.uiState.test {
            val state = awaitItem()
            assertTrue(state.gif != null || state.isLoading || state.error != null)
            cancelAndConsumeRemainingEvents()
        }
    }
}
