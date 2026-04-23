package com.aj.giphysearch.data.gifs

import de.jensklingenberg.ktorfit.http.GET
import de.jensklingenberg.ktorfit.http.Path
import de.jensklingenberg.ktorfit.http.Query

internal interface GiphyApi {

    @GET("gifs/search")
    suspend fun searchGifs(
        @Query("q") query: String,
        @Query("limit") limit: Int,
        @Query("offset") offset: Int,
    ): GiphyListResponseDto

    @GET("gifs/trending")
    suspend fun getTrendingGifs(
        @Query("limit") limit: Int,
        @Query("offset") offset: Int,
    ): GiphyListResponseDto

    @GET("gifs/{id}")
    suspend fun getGifById(@Path("id") id: String): GiphySingleResponseDto
}
