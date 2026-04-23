package com.aj.giphysearch.data.gifs

import com.aj.giphysearch.core.network.RateLimitExceededException
import com.aj.giphysearch.domain.gifs.error.GifDomainError

internal fun Throwable.toGifDomainError(): GifDomainError = when (this) {
    is RateLimitExceededException -> GifDomainError.RateLimited
    else -> GifDomainError.Unknown
}
