package com.aj.giphysearch.domain.gifs.usecase

import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository

class SearchGifsUseCase(private val repository: GifRepository) {

    suspend operator fun invoke(query: String, limit: Int, offset: Int): GifLoadResult<List<Gif>> {
        val trimmed = query.trim()
        if (trimmed.length < MIN_QUERY_LENGTH) {
            return GifLoadResult.Success(emptyList())
        }
        return repository.searchGifs(trimmed, limit, offset)
    }

    private companion object {
        private const val MIN_QUERY_LENGTH = 2
    }
}
