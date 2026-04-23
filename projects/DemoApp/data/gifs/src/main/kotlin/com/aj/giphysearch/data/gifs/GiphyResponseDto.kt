package com.aj.giphysearch.data.gifs

import kotlinx.serialization.Serializable

@Serializable
internal data class GiphyListResponseDto(
    val data: List<GifDto>,
)

@Serializable
internal data class GiphySingleResponseDto(
    val data: GifDto,
)
