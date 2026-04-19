package com.aj.giphysearch.data.mapper

import com.aj.giphysearch.data.remote.dto.GifDto
import com.aj.giphysearch.domain.model.Gif

fun GifDto.toDomain(): Gif = Gif(
    id = id,
    title = title,
    rating = rating,
    username = username,
    source = source,
    originalUrl = images.original.url,
    previewUrl = images.fixedWidth.url.ifEmpty {
        images.fixedWidthDownsampled.url.ifEmpty {
            images.original.url
        }
    },
    width = images.original.width.toIntOrNull() ?: 480,
    height = images.original.height.toIntOrNull() ?: 270,
)
