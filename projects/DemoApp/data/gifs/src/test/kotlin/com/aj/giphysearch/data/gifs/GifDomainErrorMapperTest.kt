package com.aj.giphysearch.data.gifs

import com.aj.giphysearch.core.network.RateLimitExceededException
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import org.junit.Assert.assertEquals
import org.junit.Test

class GifDomainErrorMapperTest {

    @Test
    fun `maps client rate limit exception to domain`() {
        assertEquals(GifDomainError.RateLimited, RateLimitExceededException().toGifDomainError())
    }

    @Test
    fun `maps unknown throwable to unknown domain error`() {
        assertEquals(GifDomainError.Unknown, RuntimeException("x").toGifDomainError())
    }
}
