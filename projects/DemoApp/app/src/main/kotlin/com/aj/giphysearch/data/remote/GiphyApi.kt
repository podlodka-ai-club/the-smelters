package com.aj.giphysearch.data.remote

import com.aj.giphysearch.data.remote.dto.GiphyListResponseDto
import com.aj.giphysearch.data.remote.dto.GiphySingleResponseDto
import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.get
import io.ktor.client.request.parameter

class GiphyApi(private val httpClient: HttpClient) {

    suspend fun searchGifs(query: String, limit: Int, offset: Int): GiphyListResponseDto =
        httpClient.get("gifs/search") {
            parameter("q", query)
            parameter("limit", limit)
            parameter("offset", offset)
        }.body()

    suspend fun getTrendingGifs(limit: Int, offset: Int): GiphyListResponseDto =
        httpClient.get("gifs/trending") {
            parameter("limit", limit)
            parameter("offset", offset)
        }.body()

    suspend fun getGifById(id: String): GiphySingleResponseDto =
        httpClient.get("gifs/$id").body()
}
