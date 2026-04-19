package com.aj.giphysearch.data.gifs.di

import com.aj.giphysearch.data.gifs.GifRepositoryImpl
import com.aj.giphysearch.data.gifs.GiphyApi
import com.aj.giphysearch.domain.gifs.repository.GifRepository
import org.koin.dsl.module

val gifsDataModule = module {
    single { GiphyApi(get()) }
    single<GifRepository> { GifRepositoryImpl(get()) }
}
