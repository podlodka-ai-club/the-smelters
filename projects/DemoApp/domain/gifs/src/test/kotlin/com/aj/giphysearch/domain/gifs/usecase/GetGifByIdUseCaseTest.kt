package com.aj.giphysearch.domain.gifs.usecase

import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class GetGifByIdUseCaseTest {

    @Test
    fun `invocation forwards gif id to repository`() = runTest {
        val repository = TrackingGifRepository()
        val useCase = GetGifByIdUseCase(repository)

        val result = useCase("gif_42")

        assertTrue(result is GifLoadResult.Success)
        assertEquals("gif_42", repository.lastGifId)
    }

    private class TrackingGifRepository : GifRepository {
        var lastGifId: String? = null

        override suspend fun searchGifs(
            query: String,
            limit: Int,
            offset: Int,
        ): GifLoadResult<List<Gif>> = GifLoadResult.Success(emptyList())

        override suspend fun getTrendingGifs(limit: Int, offset: Int): GifLoadResult<List<Gif>> =
            GifLoadResult.Success(emptyList())

        override suspend fun getGifById(id: String): GifLoadResult<Gif> {
            lastGifId = id
            return GifLoadResult.Success(
                Gif(
                    id = id,
                    title = "Title",
                    rating = "g",
                    username = "user",
                    source = "source",
                    originalUrl = "url",
                    previewUrl = "url",
                    width = 100,
                    height = 100,
                )
            )
        }
    }
}
