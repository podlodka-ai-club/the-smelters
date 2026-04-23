package com.aj.giphysearch.feature.search.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.paging.CombinedLoadStates
import androidx.paging.Pager
import androidx.paging.PagingConfig
import androidx.paging.PagingData
import androidx.paging.cachedIn
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.error.userMessage
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.paging.GifPagingSource
import com.aj.giphysearch.domain.gifs.usecase.SearchGifsUseCase
import com.aj.giphysearch.feature.gif.ui.GifUiEffect
import com.aj.giphysearch.feature.gif.ui.firstGifLoadFailureDomainError
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map

data class SearchUiState(
    val query: String = "",
)

@OptIn(FlowPreview::class, ExperimentalCoroutinesApi::class)
class SearchViewModel(
    private val searchGifsUseCase: SearchGifsUseCase,
) : ViewModel() {

    private val _uiState = MutableStateFlow(SearchUiState())
    val uiState: StateFlow<SearchUiState> = _uiState.asStateFlow()

    private val _uiEffects = MutableSharedFlow<GifUiEffect>(
        replay = 0,
        extraBufferCapacity = UI_EFFECT_BUFFER_CAPACITY,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val uiEffects: Flow<GifUiEffect> = _uiEffects

    val pagingData: Flow<PagingData<Gif>> = _uiState
        .map { it.query }
        .debounce(SEARCH_DEBOUNCE_MS)
        .map { it.trim() }
        .distinctUntilChanged()
        .flatMapLatest { trimmedQuery ->
            if (trimmedQuery.length < MIN_QUERY_LENGTH) {
                flowOf(PagingData.empty())
            } else {
                Pager(
                    config = PagingConfig(
                        pageSize = PAGE_SIZE,
                        prefetchDistance = PREFETCH_DISTANCE,
                        initialLoadSize = PREFETCH_DISTANCE
                    )
                ) {
                    GifPagingSource { limit, offset ->
                        searchGifsUseCase(trimmedQuery, limit, offset)
                    }
                }.flow
            }
        }
        .cachedIn(viewModelScope)

    fun onQueryChange(query: String) {
        _uiState.value = _uiState.value.copy(query = query)
    }

    fun onPagingLoadStates(loadStates: CombinedLoadStates) {
        val domainError = loadStates.firstGifLoadFailureDomainError() ?: return
        if (domainError == GifDomainError.RateLimited) {
            _uiEffects.tryEmit(GifUiEffect.ShowMessage(domainError.userMessage))
        }
    }

    private companion object {
        private const val SEARCH_DEBOUNCE_MS = 500L
        private const val MIN_QUERY_LENGTH = 2
        private const val PAGE_SIZE = 30
        private const val PREFETCH_DISTANCE = 60
        private const val UI_EFFECT_BUFFER_CAPACITY = 1
    }
}
