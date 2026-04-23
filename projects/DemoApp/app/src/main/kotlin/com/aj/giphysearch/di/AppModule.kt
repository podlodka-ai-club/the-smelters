package com.aj.giphysearch.di

import com.aj.giphysearch.BuildConfig
import com.aj.giphysearch.core.network.di.networkModule
import com.aj.giphysearch.data.gifs.di.gifsDataModule
import com.aj.giphysearch.domain.gifs.di.gifsDomainModule
import com.aj.giphysearch.feature.details.ui.DetailViewModel
import com.aj.giphysearch.feature.search.ui.SearchViewModel
import com.aj.giphysearch.feature.trending.ui.TrendingViewModel
import org.koin.core.module.dsl.viewModel
import org.koin.core.module.dsl.viewModelOf
import org.koin.dsl.module

val appModule = module {
    includes(
        networkModule(
            apiKey = BuildConfig.GIPHY_API_KEY,
            isDebug = BuildConfig.DEBUG
        ),
        gifsDataModule,
        gifsDomainModule
    )

    viewModelOf(::SearchViewModel)
    viewModelOf(::TrendingViewModel)
    viewModel { params -> DetailViewModel(get(), params.get<String>()) }
}
