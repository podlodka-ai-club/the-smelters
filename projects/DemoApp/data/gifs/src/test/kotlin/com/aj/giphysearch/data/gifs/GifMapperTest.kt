package com.aj.giphysearch.data.gifs

import org.junit.Assert.assertEquals
import org.junit.Test

class GifMapperTest {

    @Test
    fun `toDomain normalizes null and empty dto values`() {
        val domain = GifDto(
            id = "gif_1",
            title = null,
            rating = null,
            username = null,
            source = null,
            images = GifImagesDto(
                original = GifImageDto(
                    url = null,
                    width = "",
                    height = "invalid",
                ),
                fixedWidth = GifImageDto(
                    url = "",
                    width = null,
                    height = null,
                ),
                fixedWidthDownsampled = GifImageDto(
                    url = "",
                    width = null,
                    height = null,
                ),
            ),
        ).toDomain()

        assertEquals("gif_1", domain.id)
        assertEquals("", domain.title)
        assertEquals("", domain.rating)
        assertEquals("", domain.username)
        assertEquals("", domain.source)
        assertEquals("", domain.originalUrl)
        assertEquals("", domain.previewUrl)
        assertEquals(480, domain.width)
        assertEquals(270, domain.height)
    }

    @Test
    fun `toDomain preview url falls back across image variants`() {
        val domain = GifDto(
            id = "gif_2",
            images = GifImagesDto(
                original = GifImageDto(url = "original-url"),
                fixedWidth = GifImageDto(url = ""),
                fixedWidthDownsampled = GifImageDto(url = "downsampled-url"),
            ),
        ).toDomain()

        assertEquals("downsampled-url", domain.previewUrl)
    }
}
