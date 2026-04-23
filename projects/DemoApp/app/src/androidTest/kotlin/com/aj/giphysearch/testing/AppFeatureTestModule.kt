package com.aj.giphysearch.testing

import com.aj.giphysearch.feature.details.ui.DetailViewModel
import com.aj.giphysearch.feature.search.ui.SearchViewModel
import com.aj.giphysearch.feature.trending.ui.TrendingViewModel
import org.koin.core.module.dsl.viewModel
import org.koin.core.module.dsl.viewModelOf
import org.koin.dsl.module

val appFeatureTestModule = module {
    viewModelOf(::SearchViewModel)
    viewModelOf(::TrendingViewModel)
    viewModel { params -> DetailViewModel(get(), params.get<String>()) }
}
