package com.aj.giphysearch.testing

import com.aj.giphysearch.domain.gifs.fakes.FakeGifRepository
import com.aj.giphysearch.domain.gifs.repository.GifRepository
import com.aj.giphysearch.domain.gifs.usecase.GetGifByIdUseCase
import com.aj.giphysearch.domain.gifs.usecase.GetTrendingGifsUseCase
import com.aj.giphysearch.domain.gifs.usecase.SearchGifsUseCase
import org.koin.dsl.module

val appDomainTestModule = module {
    single { FakeGifRepository() }
    single<GifRepository> { get<FakeGifRepository>() }

    factory { SearchGifsUseCase(get()) }
    factory { GetTrendingGifsUseCase(get()) }
    factory { GetGifByIdUseCase(get()) }
}
