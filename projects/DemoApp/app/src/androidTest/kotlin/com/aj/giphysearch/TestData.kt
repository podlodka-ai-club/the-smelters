package com.aj.giphysearch

import com.aj.giphysearch.domain.gifs.model.Gif

/** 25 deterministic GIFs used across all UI tests. */
val TEST_GIFS: List<Gif> = (1..25).map { i ->
    Gif(
        id = "test_gif_$i",
        title = "Test GIF $i",
        rating = "g",
        username = "testuser$i",
        source = "https://example.com/source/$i",
        originalUrl = "https://example.com/original/$i.gif",
        previewUrl = "https://example.com/preview/$i.gif",
        width = 480,
        height = 270,
    )
}

val FIRST_TEST_GIF: Gif = TEST_GIFS.first()
