package com.aj.giphysearch.feature.trending

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.paging.Pager
import androidx.paging.PagingConfig
import androidx.paging.PagingData
import androidx.paging.cachedIn
import com.aj.giphysearch.data.gifs.GiphyPagingSource
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.usecase.GetTrendingGifsUseCase
import kotlinx.coroutines.flow.Flow

class TrendingViewModel(
    getTrendingGifsUseCase: GetTrendingGifsUseCase,
) : ViewModel() {

    val pagingData: Flow<PagingData<Gif>> = Pager(
        config = PagingConfig(
            pageSize = PAGE_SIZE,
            prefetchDistance = PREFETCH_DISTANCE,
            initialLoadSize = PREFETCH_DISTANCE
        )
    ) {
        GiphyPagingSource { limit, offset ->
            getTrendingGifsUseCase(limit, offset)
        }
    }.flow.cachedIn(viewModelScope)

    companion object {
        private const val PAGE_SIZE = 30
        private const val PREFETCH_DISTANCE = 60
    }
}
