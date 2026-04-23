package com.aj.giphysearch.domain.gifs.error

/**
 * Throwable envelope for APIs that require a [Throwable] (e.g. Paging [androidx.paging.PagingSource.LoadResult.Error]).
 * Prefer [GifLoadResult.Failure] at repository boundaries; map to this only in paging.
 */
class GifLoadFailureException(
    val domainError: GifDomainError,
) : Exception(
    when (domainError) {
        GifDomainError.RateLimited -> "Rate limit exceeded"
        GifDomainError.Unknown -> "Unknown error"
    },
)
