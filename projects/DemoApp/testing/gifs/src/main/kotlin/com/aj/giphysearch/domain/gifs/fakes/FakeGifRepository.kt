package com.aj.giphysearch.domain.gifs.fakes

import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository
import kotlinx.coroutines.delay

class FakeGifRepository : GifRepository {
    var searchOutcome: GifLoadResult<List<Gif>> = GifLoadResult.Success(emptyList())
    var trendingOutcome: GifLoadResult<List<Gif>> = GifLoadResult.Success(emptyList())
    var gifByIdOutcome: GifLoadResult<Gif> = GifLoadResult.Failure(GifDomainError.Unknown)
    var searchDelayMs: Long = 0L
    var trendingDelayMs: Long = 0L
    var gifByIdDelayMs: Long = 0L
    var searchCallCount: Int = 0
    var trendingCallCount: Int = 0
    var gifByIdCallCount: Int = 0
    var lastSearchQuery: String? = null
    var lastSearchLimit: Int? = null
    var lastSearchOffset: Int? = null
    var lastTrendingLimit: Int? = null
    var lastTrendingOffset: Int? = null
    var lastGifById: String? = null

    override suspend fun searchGifs(
        query: String,
        limit: Int,
        offset: Int
    ): GifLoadResult<List<Gif>> {
        searchCallCount += 1
        lastSearchQuery = query
        lastSearchLimit = limit
        lastSearchOffset = offset
        if (searchDelayMs > 0) {
            delay(searchDelayMs)
        }
        return if (offset == 0) searchOutcome else GifLoadResult.Success(emptyList())
    }

    override suspend fun getTrendingGifs(limit: Int, offset: Int): GifLoadResult<List<Gif>> {
        trendingCallCount += 1
        lastTrendingLimit = limit
        lastTrendingOffset = offset
        if (trendingDelayMs > 0) {
            delay(trendingDelayMs)
        }
        return if (offset == 0) trendingOutcome else GifLoadResult.Success(emptyList())
    }

    override suspend fun getGifById(id: String): GifLoadResult<Gif> {
        gifByIdCallCount += 1
        lastGifById = id
        if (gifByIdDelayMs > 0) {
            delay(gifByIdDelayMs)
        }
        return gifByIdOutcome
    }

    fun emitGifDetails(gif: Gif) {
        gifByIdOutcome = GifLoadResult.Success(gif)
    }
}
