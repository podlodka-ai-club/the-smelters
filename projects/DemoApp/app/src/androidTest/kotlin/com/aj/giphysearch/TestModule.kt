package com.aj.giphysearch

import com.aj.giphysearch.domain.gifs.repository.GifRepository
import com.aj.giphysearch.domain.gifs.usecase.GetGifByIdUseCase
import com.aj.giphysearch.domain.gifs.usecase.GetTrendingGifsUseCase
import com.aj.giphysearch.domain.gifs.usecase.SearchGifsUseCase
import com.aj.giphysearch.feature.details.DetailViewModel
import com.aj.giphysearch.feature.search.SearchViewModel
import com.aj.giphysearch.feature.trending.TrendingViewModel
import org.koin.core.module.dsl.viewModel
import org.koin.core.module.dsl.viewModelOf
import org.koin.dsl.module

val testAppModule = module {
    single<GifRepository> { FakeGifRepository() }

    factory { SearchGifsUseCase(get()) }
    factory { GetTrendingGifsUseCase(get()) }
    factory { GetGifByIdUseCase(get()) }

    viewModelOf(::SearchViewModel)
    viewModelOf(::TrendingViewModel)
    viewModel { params -> DetailViewModel(get(), params.get<String>()) }
}
