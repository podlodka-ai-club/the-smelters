package com.aj.giphysearch.domain.usecase

import com.aj.giphysearch.domain.model.Gif
import com.aj.giphysearch.domain.repository.GifRepository

class GetTrendingGifsUseCase(private val repository: GifRepository) {
    suspend operator fun invoke(limit: Int, offset: Int): Result<List<Gif>> =
        repository.getTrendingGifs(limit, offset)
}
