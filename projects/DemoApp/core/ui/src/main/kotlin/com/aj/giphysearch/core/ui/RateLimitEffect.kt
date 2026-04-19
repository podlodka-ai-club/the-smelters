package com.aj.giphysearch.core.ui

import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.platform.LocalContext
import androidx.paging.LoadState
import androidx.paging.compose.LazyPagingItems
import com.aj.giphysearch.domain.gifs.exception.RateLimitExceededException

@Composable
fun <T : Any> RateLimitEffect(lazyPagingItems: LazyPagingItems<T>) {
    val context = LocalContext.current

    LaunchedEffect(lazyPagingItems.loadState) {
        val errorState = lazyPagingItems.loadState.refresh as? LoadState.Error
            ?: lazyPagingItems.loadState.append as? LoadState.Error

        if (errorState?.error is RateLimitExceededException) {
            Toast.makeText(context, errorState.error.message, Toast.LENGTH_LONG).show()
        }
    }
}
