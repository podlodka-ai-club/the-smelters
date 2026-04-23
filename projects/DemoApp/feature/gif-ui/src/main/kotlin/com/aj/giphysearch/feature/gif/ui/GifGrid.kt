package com.aj.giphysearch.feature.gif.ui

import android.content.res.Configuration
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.staggeredgrid.LazyStaggeredGridState
import androidx.compose.foundation.lazy.staggeredgrid.LazyVerticalStaggeredGrid
import androidx.compose.foundation.lazy.staggeredgrid.StaggeredGridCells
import androidx.compose.foundation.lazy.staggeredgrid.StaggeredGridItemSpan
import androidx.compose.foundation.lazy.staggeredgrid.rememberLazyStaggeredGridState
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.paging.LoadState
import androidx.paging.compose.LazyPagingItems
import androidx.paging.compose.itemKey
import coil3.SingletonImageLoader
import coil3.request.ImageRequest
import com.aj.giphysearch.domain.gifs.model.Gif
import timber.log.Timber

private const val COLUMN_COUNT_PORTRAIT = 2
private const val COLUMN_COUNT_LANDSCAPE = 4
private const val PREFETCH_COUNT = 15

@Composable
fun GifGrid(
    lazyPagingItems: LazyPagingItems<Gif>,
    onGifClick: (String) -> Unit,
    modifier: Modifier = Modifier,
    contentPadding: PaddingValues = PaddingValues(8.dp),
) {
    val configuration = LocalConfiguration.current
    val columns = if (configuration.orientation == Configuration.ORIENTATION_LANDSCAPE) {
        COLUMN_COUNT_LANDSCAPE
    } else {
        COLUMN_COUNT_PORTRAIT
    }

    val gridState = rememberLazyStaggeredGridState()

    PrefetchGifsEffect(
        gridState = gridState,
        lazyPagingItems = lazyPagingItems,
    )

    LazyVerticalStaggeredGrid(
        columns = StaggeredGridCells.Fixed(columns),
        state = gridState,
        modifier = modifier.testTag("GifGrid"),
        contentPadding = contentPadding,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalItemSpacing = 8.dp,
    ) {
        items(
            count = lazyPagingItems.itemCount,
            key = lazyPagingItems.itemKey { it.id },
        ) { index ->
            val gif = lazyPagingItems[index]
            if (gif != null) {
                GifGridItem(
                    gif = gif,
                    onClick = { onGifClick(gif.id) },
                )
            }
        }

        when (lazyPagingItems.loadState.append) {
            is LoadState.Loading -> {
                item(span = StaggeredGridItemSpan.FullLine) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator()
                    }
                }
            }

            is LoadState.Error -> {
                item(span = StaggeredGridItemSpan.FullLine) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Button(onClick = { lazyPagingItems.retry() }) {
                            Text(stringResource(R.string.retry))
                        }
                    }
                }
            }

            else -> Unit
        }
    }
}

@Composable
private fun PrefetchGifsEffect(
    gridState: LazyStaggeredGridState,
    lazyPagingItems: LazyPagingItems<Gif>,
) {
    val context = LocalContext.current
    val preloadedUrls = remember { mutableSetOf<String>() }

    LaunchedEffect(gridState, lazyPagingItems) {
        val imageLoader = SingletonImageLoader.get(context)
        snapshotFlow { gridState.layoutInfo }
            .collect { layoutInfo ->
                val visibleItems = layoutInfo.visibleItemsInfo
                Timber.tag("PrefetchTest").d(
                    "visible=${visibleItems.size} itemCount=${lazyPagingItems.itemCount}",
                )
                if (visibleItems.isNotEmpty()) {
                    val lastVisible = visibleItems.last().index
                    val prefetchCount = PREFETCH_COUNT
                    val start = lastVisible + 1
                    val end = minOf(lazyPagingItems.itemCount, start + prefetchCount)

                    for (i in start until end) {
                        val gif = lazyPagingItems[i]
                        if (gif != null && preloadedUrls.add(gif.previewUrl)) {
                            val request = ImageRequest.Builder(context)
                                .data(gif.previewUrl)
                                .build()
                            imageLoader.enqueue(request)
                        }
                    }
                }
            }
    }
}
