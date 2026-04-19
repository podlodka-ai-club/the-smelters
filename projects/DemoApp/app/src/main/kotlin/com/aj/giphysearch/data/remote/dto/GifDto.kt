package com.aj.giphysearch.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class GiphyListResponseDto(
    val data: List<GifDto> = emptyList(),
    val pagination: PaginationDto = PaginationDto(),
)

@Serializable
data class GiphySingleResponseDto(
    val data: GifDto,
)

@Serializable
data class PaginationDto(
    @SerialName("total_count") val totalCount: Int = 0,
    val count: Int = 0,
    val offset: Int = 0,
)

@Serializable
data class GifDto(
    val id: String,
    val title: String = "",
    val rating: String = "",
    val username: String = "",
    val source: String = "",
    val images: GifImagesDto = GifImagesDto(),
)

@Serializable
data class GifImagesDto(
    val original: GifImageDto = GifImageDto(),
    @SerialName("fixed_width") val fixedWidth: GifImageDto = GifImageDto(),
    @SerialName("fixed_width_downsampled") val fixedWidthDownsampled: GifImageDto = GifImageDto(),
)

@Serializable
data class GifImageDto(
    val url: String = "",
    val width: String = "0",
    val height: String = "0",
    val mp4: String = "",
)
