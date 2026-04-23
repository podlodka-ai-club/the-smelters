package com.aj.giphysearch.feature.search

import androidx.paging.CombinedLoadStates
import androidx.paging.LoadState
import androidx.paging.LoadStates
import androidx.paging.AsyncPagingDataDiffer
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListUpdateCallback
import app.cash.turbine.test
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.error.GifLoadFailureException
import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.error.userMessage
import com.aj.giphysearch.domain.gifs.fakes.FakeGifRepository
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.usecase.SearchGifsUseCase
import com.aj.giphysearch.feature.gif.ui.GifUiEffect
import com.aj.giphysearch.feature.search.ui.SearchViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
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

    @Test
    fun `pagingData stays empty and does not call repository for short query`() = runTest {
        val differ = createGifDiffer()
        val collectJob = launch {
            viewModel.pagingData.collectLatest { pagingData ->
                differ.submitData(pagingData)
            }
        }

        viewModel.onQueryChange(" a ")
        advanceTimeBy(600)
        advanceUntilIdle()

        assertEquals(0, differ.itemCount)
        assertEquals(0, repository.searchCallCount)
        collectJob.cancel()
    }

    @Test
    fun `pagingData calls repository with trimmed query for valid input`() = runTest {
        repository.searchOutcome = GifLoadResult.Success(
            listOf(
                Gif(
                    id = "1",
                    title = "Cat",
                    rating = "g",
                    username = "tester",
                    source = "source",
                    originalUrl = "original",
                    previewUrl = "preview",
                    width = 100,
                    height = 100,
                )
            )
        )
        val differ = createGifDiffer()
        val collectJob = launch {
            viewModel.pagingData.collectLatest { pagingData ->
                differ.submitData(pagingData)
            }
        }

        viewModel.onQueryChange("  cats  ")
        advanceTimeBy(600)
        advanceUntilIdle()

        assertEquals(1, differ.itemCount)
        assertEquals("cats", repository.lastSearchQuery)
        assertEquals(1, repository.searchCallCount)
        collectJob.cancel()
    }

    @Test
    fun `onPagingLoadStates emits toast when rate limited`() = runTest {
        val refreshError = LoadState.Error(GifLoadFailureException(GifDomainError.RateLimited))
        val notLoading = LoadState.NotLoading(endOfPaginationReached = false)
        val source = LoadStates(
            refresh = refreshError,
            prepend = notLoading,
            append = notLoading,
        )
        val combined = CombinedLoadStates(
            refresh = refreshError,
            prepend = notLoading,
            append = notLoading,
            source = source,
        )
        viewModel.uiEffects.test {
            viewModel.onPagingLoadStates(combined)
            val effect = awaitItem()
            assertEquals(
                GifUiEffect.ShowMessage(GifDomainError.RateLimited.userMessage),
                effect,
            )
            cancelAndConsumeRemainingEvents()
        }
    }

    private fun createGifDiffer(): AsyncPagingDataDiffer<Gif> =
        AsyncPagingDataDiffer(
            diffCallback = object : DiffUtil.ItemCallback<Gif>() {
                override fun areItemsTheSame(oldItem: Gif, newItem: Gif): Boolean =
                    oldItem.id == newItem.id

                override fun areContentsTheSame(oldItem: Gif, newItem: Gif): Boolean =
                    oldItem == newItem
            },
            updateCallback = object : ListUpdateCallback {
                override fun onInserted(position: Int, count: Int) = Unit
                override fun onRemoved(position: Int, count: Int) = Unit
                override fun onMoved(fromPosition: Int, toPosition: Int) = Unit
                override fun onChanged(position: Int, count: Int, payload: Any?) = Unit
            },
            mainDispatcher = testDispatcher,
            workerDispatcher = testDispatcher,
        )
}
