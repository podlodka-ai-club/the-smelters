package com.aj.giphysearch.feature.gif.ui

import androidx.paging.CombinedLoadStates
import androidx.paging.LoadState
import com.aj.giphysearch.domain.gifs.error.GifDomainError
import com.aj.giphysearch.domain.gifs.error.GifLoadFailureException

/**
 * First domain error from our paging failures (refresh, then append, then prepend).
 */
fun CombinedLoadStates.firstGifLoadFailureDomainError(): GifDomainError? =
    listOf(refresh, append, prepend)
        .asSequence()
        .filterIsInstance<LoadState.Error>()
        .firstNotNullOfOrNull { (it.error as? GifLoadFailureException)?.domainError }
