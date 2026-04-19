package com.aj.giphysearch.data.gifs

import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository
import kotlin.coroutines.cancellation.CancellationException

internal class GifRepositoryImpl(private val api: GiphyApi) : GifRepository {

    override suspend fun searchGifs(query: String, limit: Int, offset: Int): Result<List<Gif>> =
        safeApiCall { api.searchGifs(query, limit, offset).data.map { it.toDomain() } }

    override suspend fun getTrendingGifs(limit: Int, offset: Int): Result<List<Gif>> =
        safeApiCall { api.getTrendingGifs(limit, offset).data.map { it.toDomain() } }

    override suspend fun getGifById(id: String): Result<Gif> =
        safeApiCall { api.getGifById(id).data.toDomain() }

    private suspend fun <T> safeApiCall(block: suspend () -> T): Result<T> = try {
        Result.success(block())
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        Result.failure(e)
    }
}
