package com.aj.giphysearch.domain.gifs.di

import com.aj.giphysearch.domain.gifs.usecase.GetGifByIdUseCase
import com.aj.giphysearch.domain.gifs.usecase.GetTrendingGifsUseCase
import com.aj.giphysearch.domain.gifs.usecase.SearchGifsUseCase
import org.koin.dsl.module

val gifsDomainModule = module {
    factory { SearchGifsUseCase(get()) }
    factory { GetTrendingGifsUseCase(get()) }
    factory { GetGifByIdUseCase(get()) }
}
