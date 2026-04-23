package com.aj.giphysearch.domain.gifs.usecase

import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository

class GetTrendingGifsUseCase(private val repository: GifRepository) {

    suspend operator fun invoke(limit: Int, offset: Int): GifLoadResult<List<Gif>> =
        repository.getTrendingGifs(limit, offset)
}
