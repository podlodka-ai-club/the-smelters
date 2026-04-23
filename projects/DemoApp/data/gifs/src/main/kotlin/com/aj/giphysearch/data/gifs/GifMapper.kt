package com.aj.giphysearch.data.gifs

import com.aj.giphysearch.domain.gifs.model.Gif

private const val DEFAULT_GIF_WIDTH = 480
private const val DEFAULT_GIF_HEIGHT = 270

internal fun GifDto.toDomain(): Gif = Gif(
    id = id,
    title = title.orEmpty(),
    rating = rating.orEmpty(),
    username = username.orEmpty(),
    source = source.orEmpty(),
    originalUrl = images?.original?.url.orEmpty(),
    previewUrl = images?.fixedWidth?.url.orEmpty().ifEmpty {
        images?.fixedWidthDownsampled?.url.orEmpty().ifEmpty {
            images?.original?.url.orEmpty()
        }
    },
    width = images?.original?.width?.toIntOrNull() ?: DEFAULT_GIF_WIDTH,
    height = images?.original?.height?.toIntOrNull() ?: DEFAULT_GIF_HEIGHT,
)
