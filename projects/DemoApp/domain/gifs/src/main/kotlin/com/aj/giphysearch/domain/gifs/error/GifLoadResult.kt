package com.aj.giphysearch.domain.gifs.error

/**
 * Typed load outcome for repository / use case calls (replaces [kotlin.Result] for domain-shaped errors).
 */
sealed class GifLoadResult<out T> {
    data class Success<T>(val data: T) : GifLoadResult<T>()
    data class Failure(val error: GifDomainError) : GifLoadResult<Nothing>()
}
