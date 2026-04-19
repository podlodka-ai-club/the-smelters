package com.aj.giphysearch.domain.usecase

import com.aj.giphysearch.domain.model.Gif
import com.aj.giphysearch.domain.repository.GifRepository

class SearchGifsUseCase(private val repository: GifRepository) {
    suspend operator fun invoke(query: String, limit: Int, offset: Int): Result<List<Gif>> {
        val trimmed = query.trim()
        if (trimmed.length < MIN_QUERY_LENGTH) {
            return Result.success(emptyList())
        }
        return repository.searchGifs(trimmed, limit, offset)
    }

    companion object {
        private const val MIN_QUERY_LENGTH = 2
    }
}
