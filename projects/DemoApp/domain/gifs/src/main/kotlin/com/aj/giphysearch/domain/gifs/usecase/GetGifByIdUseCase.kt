package com.aj.giphysearch.domain.gifs.usecase

import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.repository.GifRepository

class GetGifByIdUseCase(private val repository: GifRepository) {
    suspend operator fun invoke(id: String): Result<Gif> =
        repository.getGifById(id)
}
