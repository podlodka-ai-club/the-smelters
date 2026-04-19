package com.aj.giphysearch.data.paging

import androidx.paging.PagingSource
import androidx.paging.PagingState
import com.aj.giphysearch.domain.model.Gif

class GiphyPagingSource(
    private val loadPage: suspend (limit: Int, offset: Int) -> Result<List<Gif>>,
) : PagingSource<Int, Gif>() {

    override fun getRefreshKey(state: PagingState<Int, Gif>): Int? {
        return state.anchorPosition?.let { anchor ->
            state.closestPageToPosition(anchor)?.let { page ->
                page.prevKey?.plus(state.config.pageSize) ?: page.nextKey?.minus(state.config.pageSize)
            }
        }
    }

    override suspend fun load(params: LoadParams<Int>): LoadResult<Int, Gif> {
        val offset = params.key ?: 0
        return loadPage(params.loadSize, offset).fold(
            onSuccess = { gifs ->
                LoadResult.Page(
                    data = gifs,
                    prevKey = if (offset == 0) null else maxOf(0, offset - params.loadSize),
                    nextKey = if (gifs.isEmpty()) null else offset + gifs.size,
                )
            },
            onFailure = { error ->
                LoadResult.Error(error)
            },
        )
    }
}
