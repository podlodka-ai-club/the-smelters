package com.aj.giphysearch.domain.gifs.model

import androidx.compose.runtime.Immutable

@Immutable
data class Gif(
    val id: String,
    val title: String,
    val rating: String,
    val username: String,
    val source: String,
    val originalUrl: String,
    val previewUrl: String,
    val width: Int,
    val height: Int,
)
