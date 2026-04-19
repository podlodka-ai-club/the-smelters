package com.aj.giphysearch

import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository

class FakeGifRepository : GifRepository {

    var searchResult: Result<List<Gif>> = Result.success(emptyList())
    var trendingResult: Result<List<Gif>> = Result.success(emptyList())
    var gifByIdResult: Result<Gif> = Result.success(fakeGif("1"))

    var searchCalls = mutableListOf<Triple<String, Int, Int>>()
    var trendingCalls = mutableListOf<Pair<Int, Int>>()
    var gifByIdCalls = mutableListOf<String>()

    override suspend fun searchGifs(query: String, limit: Int, offset: Int): Result<List<Gif>> {
        searchCalls.add(Triple(query, limit, offset))
        return searchResult
    }

    override suspend fun getTrendingGifs(limit: Int, offset: Int): Result<List<Gif>> {
        trendingCalls.add(Pair(limit, offset))
        return trendingResult
    }

    override suspend fun getGifById(id: String): Result<Gif> {
        gifByIdCalls.add(id)
        return gifByIdResult
    }
}

fun fakeGif(id: String) = Gif(
    id = id,
    title = "GIF $id",
    rating = "g",
    username = "user$id",
    source = "https://example.com/$id",
    originalUrl = "https://media.giphy.com/original/$id.gif",
    previewUrl = "https://media.giphy.com/preview/$id.gif",
    width = 480,
    height = 270,
)

fun fakeGifList(count: Int, offset: Int = 0) = (offset until offset + count).map { fakeGif(it.toString()) }
