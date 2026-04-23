package com.aj.giphysearch.feature.search.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.paging.LoadState
import androidx.paging.compose.LazyPagingItems
import androidx.paging.compose.collectAsLazyPagingItems
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.feature.gif.ui.CollectGifUiEffects
import com.aj.giphysearch.feature.gif.ui.GifGrid
import com.aj.giphysearch.feature.search.R
import org.koin.androidx.compose.koinViewModel

@Composable
fun SearchScreen(
    onGifClick: (String) -> Unit,
    contentPadding: PaddingValues = PaddingValues(0.dp),
    viewModel: SearchViewModel = koinViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val pagingItems = viewModel.pagingData.collectAsLazyPagingItems()

    CollectGifUiEffects(viewModel.uiEffects)
    LaunchedEffect(pagingItems.loadState) {
        viewModel.onPagingLoadStates(pagingItems.loadState)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(contentPadding)
            .testTag("SearchScreen"),
    ) {
        SearchTextField(
            query = uiState.query,
            onQueryChange = viewModel::onQueryChange,
        )

        SearchContent(
            query = uiState.query,
            pagingItems = pagingItems,
            onGifClick = onGifClick,
        )
    }
}

@Composable
private fun SearchTextField(
    query: String,
    onQueryChange: (String) -> Unit,
) {
    OutlinedTextField(
        value = query,
        onValueChange = onQueryChange,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp)
            .testTag("SearchField"),
        placeholder = { Text(stringResource(R.string.search_gifs_placeholder)) },
        leadingIcon = {
            Icon(
                imageVector = Icons.Default.Search,
                contentDescription = null,
            )
        },
        trailingIcon = {
            if (query.isNotEmpty()) {
                IconButton(
                    onClick = { onQueryChange("") },
                    modifier = Modifier.testTag("SearchClearButton"),
                ) {
                    Icon(
                        imageVector = Icons.Default.Clear,
                        contentDescription = stringResource(R.string.search_clear_content_description),
                    )
                }
            }
        },
        singleLine = true,
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
    )
}

private const val MIN_QUERY_LENGTH = 2

@Composable
private fun SearchContent(
    query: String,
    pagingItems: LazyPagingItems<Gif>,
    onGifClick: (String) -> Unit,
) {
    Box(modifier = Modifier.fillMaxSize()) {
        val loadState = pagingItems.loadState.refresh
        when {
            query.trim().length < MIN_QUERY_LENGTH -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag("SearchPrompt"),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(stringResource(R.string.search_min_query_prompt))
                }
            }

            loadState is LoadState.Loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag("SearchLoading"),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator()
                }
            }

            loadState is LoadState.Error -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag("SearchErrorState"),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(stringResource(R.string.search_failed_to_load_gifs))
                        TextButton(
                            onClick = { pagingItems.retry() },
                            modifier = Modifier.testTag("SearchRetryButton"),
                        ) {
                            Text(stringResource(R.string.search_retry))
                        }
                    }
                }
            }

            pagingItems.itemCount == 0 && loadState is LoadState.NotLoading -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag("SearchEmptyState"),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(stringResource(R.string.search_no_gifs_found))
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
