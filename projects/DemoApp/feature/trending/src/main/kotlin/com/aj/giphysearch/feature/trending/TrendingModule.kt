package com.aj.giphysearch.feature.trending

import org.koin.androidx.viewmodel.dsl.viewModelOf
import org.koin.dsl.module

val trendingModule = module {
    viewModelOf(::TrendingViewModel)
}
