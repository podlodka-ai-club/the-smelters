package com.aj.giphysearch.domain.gifs.usecase

import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchGifsUseCaseTest {

    private val repository = object : GifRepository {
        override suspend fun searchGifs(query: String, limit: Int, offset: Int): Result<List<Gif>> {
            return Result.success(listOf(fakeGif("1")))
        }
        override suspend fun getTrendingGifs(limit: Int, offset: Int): Result<List<Gif>> {
            return Result.success(listOf(fakeGif("trending")))
        }
        override suspend fun getGifById(id: String): Result<Gif> {
            return Result.success(fakeGif(id))
        }
    }

    private val useCase = SearchGifsUseCase(repository)

    @Test
    fun `when query is too short, return empty list`() = runTest {
        val result = useCase("a", 25, 0)
        assertTrue(result.isSuccess)
        assertEquals(0, result.getOrNull()?.size)
    }

    @Test
    fun `when query is long enough, call repository`() = runTest {
        val result = useCase("abc", 25, 0)
        assertTrue(result.isSuccess)
        assertEquals(1, result.getOrNull()?.size)
    }

    private fun fakeGif(id: String) = Gif(
        id = id,
        title = "Title",
        rating = "g",
        username = "user",
        source = "source",
        originalUrl = "url",
        previewUrl = "url",
        width = 100,
        height = 100
    )
}
