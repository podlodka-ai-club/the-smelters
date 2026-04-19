package com.aj.giphysearch.feature.search

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
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.paging.LoadState
import androidx.paging.compose.collectAsLazyPagingItems
import com.aj.giphysearch.core.ui.GifGrid
import com.aj.giphysearch.domain.gifs.model.Gif
import org.koin.androidx.compose.koinViewModel

@Composable
fun SearchScreen(
    onGifClick: (String) -> Unit,
    contentPadding: PaddingValues = PaddingValues(0.dp),
    viewModel: SearchViewModel = koinViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val pagingItems = viewModel.pagingData.collectAsLazyPagingItems()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(contentPadding)
            .testTag("search_screen"),
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
            .testTag("search_field"),
        placeholder = { Text("Search GIFs…") },
        leadingIcon = {
            Icon(
                imageVector = Icons.Default.Search,
                contentDescription = null,
            )
        },
        trailingIcon = {
            if (query.isNotEmpty()) {
                IconButton(onClick = { onQueryChange("") }) {
                    Icon(
                        imageVector = Icons.Default.Clear,
                        contentDescription = "Clear",
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
    pagingItems: androidx.paging.compose.LazyPagingItems<Gif>,
    onGifClick: (String) -> Unit,
) {
    Box(modifier = Modifier.fillMaxSize()) {
        val loadState = pagingItems.loadState.refresh
        when {
            query.trim().length < MIN_QUERY_LENGTH -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag("search_prompt"),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("Type at least 2 characters to search")
                }
            }
            loadState is LoadState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            loadState is LoadState.Error -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Failed to load GIFs")
                        TextButton(onClick = { pagingItems.retry() }) {
                            Text("Retry")
                        }
                    }
                }
            }
            pagingItems.itemCount == 0 && loadState is LoadState.NotLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("No GIFs found")
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
