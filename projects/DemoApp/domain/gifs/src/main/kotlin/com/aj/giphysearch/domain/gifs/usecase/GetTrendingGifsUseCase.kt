package com.aj.giphysearch.domain.gifs.usecase

import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository

class GetTrendingGifsUseCase(private val repository: GifRepository) {
    suspend operator fun invoke(limit: Int, offset: Int): Result<List<Gif>> =
        repository.getTrendingGifs(limit, offset)
}
