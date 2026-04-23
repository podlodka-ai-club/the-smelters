package com.aj.giphysearch.data.gifs

import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository
import kotlin.coroutines.cancellation.CancellationException

internal class GifRepositoryImpl(private val api: GiphyApi) : GifRepository {

    override suspend fun searchGifs(
        query: String,
        limit: Int,
        offset: Int
    ): GifLoadResult<List<Gif>> =
        safeApiCall { api.searchGifs(query, limit, offset).data.map { it.toDomain() } }

    override suspend fun getTrendingGifs(limit: Int, offset: Int): GifLoadResult<List<Gif>> =
        safeApiCall { api.getTrendingGifs(limit, offset).data.map { it.toDomain() } }

    override suspend fun getGifById(id: String): GifLoadResult<Gif> =
        safeApiCall { api.getGifById(id).data.toDomain() }

    private suspend fun <T> safeApiCall(block: suspend () -> T): GifLoadResult<T> = try {
        GifLoadResult.Success(block())
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        GifLoadResult.Failure(e.toGifDomainError())
    }
}
