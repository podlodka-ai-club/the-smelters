package com.aj.giphysearch

import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository

class FakeGifRepository : GifRepository {

    override suspend fun searchGifs(query: String, limit: Int, offset: Int): Result<List<Gif>> =
        Result.success(TEST_GIFS.drop(offset).take(limit))

    override suspend fun getTrendingGifs(limit: Int, offset: Int): Result<List<Gif>> =
        Result.success(TEST_GIFS.drop(offset).take(limit))

    override suspend fun getGifById(id: String): Result<Gif> =
        Result.success(TEST_GIFS.find { it.id == id } ?: FIRST_TEST_GIF)
}
