package com.aj.giphysearch.domain.gifs.usecase

import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository

class GetGifByIdUseCase(private val repository: GifRepository) {

    suspend operator fun invoke(id: String): GifLoadResult<Gif> =
        repository.getGifById(id)
}
