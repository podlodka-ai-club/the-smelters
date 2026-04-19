package com.aj.giphysearch.domain.gifs.repository

import com.aj.giphysearch.domain.gifs.model.Gif

interface GifRepository {
    suspend fun searchGifs(query: String, limit: Int, offset: Int): Result<List<Gif>>
    suspend fun getTrendingGifs(limit: Int, offset: Int): Result<List<Gif>>
    suspend fun getGifById(id: String): Result<Gif>
}
