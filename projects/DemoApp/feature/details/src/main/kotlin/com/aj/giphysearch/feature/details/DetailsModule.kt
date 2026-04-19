package com.aj.giphysearch.feature.details

import org.koin.androidx.viewmodel.dsl.viewModel
import org.koin.dsl.module

val detailsModule = module {
    viewModel { (gifId: String) -> DetailViewModel(get(), gifId) }
}
