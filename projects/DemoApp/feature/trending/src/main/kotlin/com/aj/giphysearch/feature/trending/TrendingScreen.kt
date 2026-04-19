package com.aj.giphysearch.feature.trending

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.paging.LoadState
import androidx.paging.compose.collectAsLazyPagingItems
import com.aj.giphysearch.core.ui.GifGrid
import org.koin.androidx.compose.koinViewModel

@Composable
fun TrendingScreen(
    onGifClick: (String) -> Unit,
    contentPadding: PaddingValues = PaddingValues(0.dp),
    viewModel: TrendingViewModel = koinViewModel(),
) {
    val pagingItems = viewModel.pagingData.collectAsLazyPagingItems()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(contentPadding)
            .testTag("trending_screen"),
    ) {
        when {
            pagingItems.loadState.refresh is LoadState.Loading -> {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            }
            pagingItems.loadState.refresh is LoadState.Error -> {
                Column(
                    modifier = Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("Failed to load GIFs")
                    TextButton(onClick = { pagingItems.retry() }) {
                        Text("Retry")
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
