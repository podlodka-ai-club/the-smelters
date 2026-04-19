package com.aj.giphysearch.domain.usecase

import com.aj.giphysearch.domain.model.Gif
import com.aj.giphysearch.domain.repository.GifRepository

class GetGifByIdUseCase(private val repository: GifRepository) {
    suspend operator fun invoke(id: String): Result<Gif> =
        repository.getGifById(id)
}
