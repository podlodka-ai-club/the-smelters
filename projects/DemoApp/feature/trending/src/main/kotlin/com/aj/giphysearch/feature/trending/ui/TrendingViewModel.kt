package com.aj.giphysearch.feature.trending.ui

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
import com.aj.giphysearch.domain.gifs.usecase.GetTrendingGifsUseCase
import com.aj.giphysearch.feature.gif.ui.GifUiEffect
import com.aj.giphysearch.feature.gif.ui.firstGifLoadFailureDomainError
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow

class TrendingViewModel(
    getTrendingGifsUseCase: GetTrendingGifsUseCase,
) : ViewModel() {

    private val _uiEffects = MutableSharedFlow<GifUiEffect>(
        replay = 0,
        extraBufferCapacity = UI_EFFECT_BUFFER_CAPACITY,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val uiEffects: Flow<GifUiEffect> = _uiEffects

    val pagingData: Flow<PagingData<Gif>> = Pager(
        config = PagingConfig(
            pageSize = PAGE_SIZE,
            prefetchDistance = PREFETCH_DISTANCE,
            initialLoadSize = PREFETCH_DISTANCE
        )
    ) {
        GifPagingSource { limit, offset ->
            getTrendingGifsUseCase(limit, offset)
        }
    }.flow.cachedIn(viewModelScope)

    fun onPagingLoadStates(loadStates: CombinedLoadStates) {
        val domainError = loadStates.firstGifLoadFailureDomainError() ?: return
        if (domainError == GifDomainError.RateLimited) {
            _uiEffects.tryEmit(GifUiEffect.ShowMessage(domainError.userMessage))
        }
    }

    private companion object {
        private const val PAGE_SIZE = 30
        private const val PREFETCH_DISTANCE = 60
        private const val UI_EFFECT_BUFFER_CAPACITY = 1
    }
}
