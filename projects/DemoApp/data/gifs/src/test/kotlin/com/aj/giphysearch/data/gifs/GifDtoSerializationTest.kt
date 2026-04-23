package com.aj.giphysearch.data.gifs

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.MissingFieldException
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.fail
import org.junit.Test

@OptIn(ExperimentalSerializationApi::class)
class GifDtoSerializationTest {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun `decodes with missing optional gif fields`() {
        val dto = json.decodeFromString<GifDto>(
            """
            {
              "id": "gif_1"
            }
            """.trimIndent(),
        )

        assertEquals("gif_1", dto.id)
        assertNull(dto.title)
        assertNull(dto.images)
    }

    @Test
    fun `decodes with explicit null optional gif fields`() {
        val dto = json.decodeFromString<GifDto>(
            """
            {
              "id": "gif_1",
              "title": null,
              "images": null
            }
            """.trimIndent(),
        )

        assertEquals("gif_1", dto.id)
        assertNull(dto.title)
        assertNull(dto.images)
    }

    @Test
    fun `fails when required field is missing`() {
        try {
            json.decodeFromString<GifDto>(
                """
                {
                  "title": "missing id"
                }
                """.trimIndent(),
            )
            fail("Expected MissingFieldException when required id is absent")
        } catch (exception: MissingFieldException) {
            assertEquals(true, exception.message.orEmpty().contains("id"))
        }
    }
}
