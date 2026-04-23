package com.aj.giphysearch.feature.trending.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.paging.LoadState
import androidx.paging.compose.collectAsLazyPagingItems
import com.aj.giphysearch.feature.gif.ui.R as GifUiR
import com.aj.giphysearch.feature.gif.ui.CollectGifUiEffects
import com.aj.giphysearch.feature.gif.ui.GifGrid
import org.koin.androidx.compose.koinViewModel

@Composable
fun TrendingScreen(
    onGifClick: (String) -> Unit,
    contentPadding: PaddingValues = PaddingValues(0.dp),
    viewModel: TrendingViewModel = koinViewModel(),
) {
    val pagingItems = viewModel.pagingData.collectAsLazyPagingItems()

    CollectGifUiEffects(viewModel.uiEffects)
    LaunchedEffect(pagingItems.loadState) {
        viewModel.onPagingLoadStates(pagingItems.loadState)
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(contentPadding)
            .testTag("TrendingScreen"),
    ) {
        when (pagingItems.loadState.refresh) {
            is LoadState.Loading -> {
                CircularProgressIndicator(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .testTag("TrendingLoading"),
                )
            }

            is LoadState.Error -> {
                Column(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .testTag("TrendingErrorState"),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(stringResource(GifUiR.string.failed_to_load_gifs))
                    TextButton(
                        onClick = { pagingItems.retry() },
                        modifier = Modifier.testTag("TrendingRetryButton"),
                    ) {
                        Text(stringResource(GifUiR.string.retry))
                    }
                }
            }

            else -> {
                GifGrid(
                    lazyPagingItems = pagingItems,
                    onGifClick = onGifClick,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }
}
