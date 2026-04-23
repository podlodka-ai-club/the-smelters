package com.aj.giphysearch.feature.details.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aj.giphysearch.domain.gifs.error.GifLoadResult
import com.aj.giphysearch.domain.gifs.error.userMessage
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.usecase.GetGifByIdUseCase
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.flow.stateIn

data class DetailUiState(
    val gif: Gif? = null,
    val isLoading: Boolean = true,
    val error: String? = null,
)

@OptIn(ExperimentalCoroutinesApi::class)
class DetailViewModel(
    private val getGifByIdUseCase: GetGifByIdUseCase,
    private val gifId: String,
) : ViewModel() {
    private val refreshTrigger = MutableSharedFlow<Unit>(
        replay = 1,
        extraBufferCapacity = 1,
    )

    val uiState: StateFlow<DetailUiState> = refreshTrigger
        .onStart { emit(Unit) }
        .flatMapLatest {
            flow {
                emit(DetailUiState(isLoading = true))
                val nextState = when (val outcome = getGifByIdUseCase(gifId)) {
                    is GifLoadResult.Success ->
                        DetailUiState(gif = outcome.data, isLoading = false)
                    is GifLoadResult.Failure ->
                        DetailUiState(
                            isLoading = false,
                            error = outcome.error.userMessage,
                        )
                }
                emit(nextState)
            }
        }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
            initialValue = DetailUiState(),
        )

    fun retry() {
        refreshTrigger.tryEmit(Unit)
    }

    private companion object {
        private const val STOP_TIMEOUT_MILLIS = 5_000L
    }
}
