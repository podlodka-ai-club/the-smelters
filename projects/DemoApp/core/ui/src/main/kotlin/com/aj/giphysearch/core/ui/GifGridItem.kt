package com.aj.giphysearch.core.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.aj.giphysearch.domain.gifs.model.Gif

@Composable
fun GifGridItem(
    gif: Gif,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val aspectRatio = if (gif.width > 0 && gif.height > 0) {
        gif.width.toFloat() / gif.height.toFloat()
    } else {
        1f
    }

    AsyncImage(
        model = gif.previewUrl,
        contentDescription = gif.title,
        contentScale = ContentScale.Crop,
        modifier = modifier
            .fillMaxWidth()
            .aspectRatio(aspectRatio)
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
            .testTag("gif_item"),
    )
}
