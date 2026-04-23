package com.aj.giphysearch.feature.gif.ui

import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.flow.Flow

@Composable
fun CollectGifUiEffects(effects: Flow<GifUiEffect>) {
    val context = LocalContext.current
    LaunchedEffect(effects) {
        effects.collect { effect ->
            when (effect) {
                is GifUiEffect.ShowMessage ->
                    Toast.makeText(context, effect.message, Toast.LENGTH_LONG).show()
            }
        }
    }
}
