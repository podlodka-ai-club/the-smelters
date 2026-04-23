package com.aj.giphysearch.feature.gif.ui

/**
 * One-shot UI actions produced by feature ViewModels (toasts, snackbars, etc.).
 */
sealed interface GifUiEffect {
    data class ShowMessage(val message: String) : GifUiEffect
}
