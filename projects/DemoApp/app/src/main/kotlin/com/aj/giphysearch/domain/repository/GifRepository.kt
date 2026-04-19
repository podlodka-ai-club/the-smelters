package com.aj.giphysearch.domain.repository

import com.aj.giphysearch.domain.model.Gif

/**
 * Repository interface for fetching GIFs from the remote data source.
 * Acts as the single source of truth for the domain layer.
 */
interface GifRepository {

    /**
     * Searches for GIFs matching the given query string.
     *
     * @param query The search term to query for.
     * @param limit The maximum number of items to return.
     * @param offset The starting position of the results.
     * @return A [Result] containing a list of [Gif]s on success, or an error on failure.
     */
    suspend fun searchGifs(query: String, limit: Int, offset: Int): Result<List<Gif>>

    /**
     * Fetches the current trending GIFs.
     *
     * @param limit The maximum number of items to return.
     * @param offset The starting position of the results.
     * @return A [Result] containing a list of [Gif]s on success, or an error on failure.
     */
    suspend fun getTrendingGifs(limit: Int, offset: Int): Result<List<Gif>>

    /**
     * Fetches a specific GIF by its unique identifier.
     *
     * @param id The unique ID of the GIF.
     * @return A [Result] containing the [Gif] on success, or an error on failure.
     */
    suspend fun getGifById(id: String): Result<Gif>
}
