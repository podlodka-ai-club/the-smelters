package com.aj.giphysearch.data.gifs.di

import com.aj.giphysearch.data.gifs.GifRepositoryImpl
import com.aj.giphysearch.data.gifs.GiphyApi
import com.aj.giphysearch.data.gifs.createGiphyApi
import com.aj.giphysearch.domain.gifs.repository.GifRepository
import de.jensklingenberg.ktorfit.ktorfit
import io.ktor.client.HttpClient
import org.koin.dsl.module

val gifsDataModule = module {
    single {
        val client: HttpClient = get()
        ktorfit {
            baseUrl("https://api.giphy.com/v1/")
            httpClient(client)
        }
    }
    single<GiphyApi> { get<de.jensklingenberg.ktorfit.Ktorfit>().createGiphyApi() }
    single<GifRepository> { GifRepositoryImpl(get()) }
}
