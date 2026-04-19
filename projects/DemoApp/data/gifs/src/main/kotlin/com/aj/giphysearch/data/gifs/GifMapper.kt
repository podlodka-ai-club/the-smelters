package com.aj.giphysearch.data.gifs

import com.aj.giphysearch.domain.gifs.model.Gif

internal fun GifDto.toDomain(): Gif = Gif(
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
