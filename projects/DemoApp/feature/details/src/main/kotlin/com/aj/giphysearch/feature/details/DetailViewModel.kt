package com.aj.giphysearch.feature.details

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aj.giphysearch.domain.gifs.model.Gif
import com.aj.giphysearch.domain.gifs.usecase.GetGifByIdUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DetailUiState(
    val gif: Gif? = null,
    val isLoading: Boolean = true,
    val error: String? = null,
)

class DetailViewModel(
    private val getGifByIdUseCase: GetGifByIdUseCase,
    private val gifId: String,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DetailUiState())
    val uiState: StateFlow<DetailUiState> = _uiState.asStateFlow()

    init {
        loadGif()
    }

    fun retry() = loadGif()

    private fun loadGif() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            getGifByIdUseCase(gifId)
                .onSuccess { gif ->
                    _uiState.update { it.copy(gif = gif, isLoading = false) }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isLoading = false, error = error.message ?: "Unknown error")
                    }
                }
        }
    }
}
