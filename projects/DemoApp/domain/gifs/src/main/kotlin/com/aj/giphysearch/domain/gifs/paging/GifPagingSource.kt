package com.aj.giphysearch.domain.gifs.paging

import androidx.paging.PagingSource
import androidx.paging.PagingState
import com.aj.giphysearch.domain.gifs.error.GifLoadFailureException
import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.model.Gif

/**
 * Offset-based [PagingSource] for GIF lists.
 *
 * The caller provides [loadPage], allowing presentation code to build pagers without importing
 * concrete data-layer classes.
 */
class GifPagingSource(
    private val loadPage: suspend (limit: Int, offset: Int) -> GifLoadResult<List<Gif>>,
) : PagingSource<Int, Gif>() {

    override fun getRefreshKey(state: PagingState<Int, Gif>): Int? {
        return state.anchorPosition?.let { anchor ->
            state.closestPageToPosition(anchor)?.let { page ->
                page.prevKey?.plus(state.config.pageSize)
                    ?: page.nextKey?.minus(state.config.pageSize)
            }
        }
    }

    override suspend fun load(params: LoadParams<Int>): LoadResult<Int, Gif> {
        val offset = params.key ?: 0
        return when (val outcome = loadPage(params.loadSize, offset)) {
            is GifLoadResult.Success -> {
                val gifs = outcome.data
                LoadResult.Page(
                    data = gifs,
                    prevKey = if (offset == 0) null else maxOf(0, offset - params.loadSize),
                    nextKey = if (gifs.isEmpty()) null else offset + gifs.size,
                )
            }

            is GifLoadResult.Failure -> LoadResult.Error(GifLoadFailureException(outcome.error))
        }
    }
}
