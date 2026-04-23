package com.aj.giphysearch.domain.gifs.error

/**
 * Business-facing failure semantics for GIF loading.
 */
sealed interface GifDomainError {
    data object RateLimited : GifDomainError
    data object Unknown : GifDomainError
}

val GifDomainError.userMessage: String
    get() = when (this) {
        GifDomainError.RateLimited ->
            "Rate limit of 100 requests per hour exceeded. Please wait to make more requests."
        GifDomainError.Unknown -> "Something went wrong"
    }
