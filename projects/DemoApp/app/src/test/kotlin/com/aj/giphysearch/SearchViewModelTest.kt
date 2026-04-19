package com.aj.giphysearch

import app.cash.turbine.test
import com.aj.giphysearch.domain.gifs.usecase.SearchGifsUseCase
import com.aj.giphysearch.feature.search.SearchViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SearchViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var repository: FakeGifRepository
    private lateinit var viewModel: SearchViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        repository = FakeGifRepository()
        viewModel = SearchViewModel(SearchGifsUseCase(repository))
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial state has empty query`() = runTest {
        viewModel.uiState.test {
            val state = awaitItem()
            assertEquals("", state.query)
            cancelAndConsumeRemainingEvents()
        }
    }

    @Test
    fun `onQueryChange updates query state`() = runTest {
        viewModel.uiState.test {
            awaitItem() // initial empty state

            viewModel.onQueryChange("cats")
            val updated = awaitItem()
            assertEquals("cats", updated.query)

            cancelAndConsumeRemainingEvents()
        }
    }

    @Test
    fun `onQueryChange to empty clears query`() = runTest {
        viewModel.onQueryChange("cats")

        viewModel.uiState.test {
            awaitItem() // "cats"
            viewModel.onQueryChange("")
            val cleared = awaitItem()
            assertEquals("", cleared.query)
            cancelAndConsumeRemainingEvents()
        }
    }
}
