package com.aj.giphysearch.data.gifs

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
internal data class GifDto(
    val id: String,
    val title: String? = null,
    val rating: String? = null,
    val username: String? = null,
    val source: String? = null,
    val images: GifImagesDto? = null,
)

@Serializable
internal data class GifImagesDto(
    val original: GifImageDto? = null,
    @SerialName("fixed_width") val fixedWidth: GifImageDto? = null,
    @SerialName("fixed_width_downsampled") val fixedWidthDownsampled: GifImageDto? = null,
)

@Serializable
internal data class GifImageDto(
    val url: String? = null,
    val width: String? = null,
    val height: String? = null,
)
