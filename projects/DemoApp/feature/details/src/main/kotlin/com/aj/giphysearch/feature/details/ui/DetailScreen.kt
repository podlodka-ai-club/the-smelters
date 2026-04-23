package com.aj.giphysearch.feature.details.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.AsyncImage
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.feature.details.R
import org.koin.androidx.compose.koinViewModel
import org.koin.core.parameter.parametersOf

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailScreen(
    gifId: String,
    onBack: () -> Unit,
    viewModel: DetailViewModel = koinViewModel(parameters = { parametersOf(gifId) }),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        modifier = Modifier.testTag("DetailScreen"),
        topBar = {
            TopAppBar(
                title = { Text(uiState.gif?.title ?: "") },
                navigationIcon = {
                    IconButton(
                        onClick = onBack,
                        modifier = Modifier.testTag("BackButton")
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.detail_back_content_description),
                        )
                    }
                },
            )
        },
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues),
            contentAlignment = Alignment.Center,
        ) {
            when {
                uiState.isLoading ->
                    CircularProgressIndicator(modifier = Modifier.testTag("DetailLoading"))
                uiState.error != null -> {
                    Column(
                        modifier = Modifier.testTag("DetailErrorState"),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Text(uiState.error ?: stringResource(R.string.detail_failed_to_load_gif))
                        TextButton(
                            onClick = viewModel::retry,
                            modifier = Modifier.testTag("DetailRetryButton"),
                        ) {
                            Text(stringResource(R.string.detail_retry))
                        }
                    }
                }

                uiState.gif != null -> {
                    val gif = uiState.gif!!
                    DetailContent(gif = gif)
                }
            }
        }
    }
}

@Composable
private fun DetailContent(gif: Gif) {
    val aspectRatio = if (gif.width > 0 && gif.height > 0) {
        gif.width.toFloat() / gif.height.toFloat()
    } else {
        1f
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
    ) {
        AsyncImage(
            model = gif.originalUrl,
            contentDescription = gif.title,
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(aspectRatio),
        )

        Column(modifier = Modifier.padding(16.dp)) {
            if (gif.title.isNotBlank()) {
                Text(
                    text = gif.title,
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.testTag("GifTitle_${gif.title}")
                )
                Spacer(modifier = Modifier.height(8.dp))
            }

            if (gif.rating.isNotBlank()) {
                Box(
                    modifier = Modifier
                        .padding(vertical = 4.dp)
                        .background(
                            color = MaterialTheme.colorScheme.secondaryContainer,
                            shape = MaterialTheme.shapes.small,
                        )
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                ) {
                    Text(
                        text = stringResource(R.string.detail_rating_label, gif.rating.uppercase()),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSecondaryContainer,
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
            }

            if (gif.username.isNotBlank()) {
                Text(
                    text = stringResource(R.string.detail_by_username, gif.username),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(modifier = Modifier.height(4.dp))
            }

            if (gif.source.isNotBlank()) {
                Text(
                    text = gif.source,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }
    }
}
