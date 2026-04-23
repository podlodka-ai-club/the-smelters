package com.aj.giphysearch.domain.gifs.usecase

import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class GetTrendingGifsUseCaseTest {

    @Test
    fun `invocation forwards limit and offset to repository`() = runTest {
        val repository = TrackingGifRepository()
        val useCase = GetTrendingGifsUseCase(repository)

        val result = useCase(limit = 30, offset = 60)

        assertTrue(result is GifLoadResult.Success)
        assertEquals(30, repository.lastTrendingLimit)
        assertEquals(60, repository.lastTrendingOffset)
    }

    private class TrackingGifRepository : GifRepository {
        var lastTrendingLimit: Int? = null
        var lastTrendingOffset: Int? = null

        override suspend fun searchGifs(
            query: String,
            limit: Int,
            offset: Int,
        ): GifLoadResult<List<Gif>> = GifLoadResult.Success(emptyList())

        override suspend fun getTrendingGifs(limit: Int, offset: Int): GifLoadResult<List<Gif>> {
            lastTrendingLimit = limit
            lastTrendingOffset = offset
            return GifLoadResult.Success(emptyList())
        }

        override suspend fun getGifById(id: String): GifLoadResult<Gif> =
            GifLoadResult.Failure(GifDomainError.Unknown)
    }
}
