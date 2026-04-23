package com.aj.giphysearch.domain.gifs.repository

import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.model.Gif

interface GifRepository {
    suspend fun searchGifs(query: String, limit: Int, offset: Int): GifLoadResult<List<Gif>>
    suspend fun getTrendingGifs(limit: Int, offset: Int): GifLoadResult<List<Gif>>
    suspend fun getGifById(id: String): GifLoadResult<Gif>
}
