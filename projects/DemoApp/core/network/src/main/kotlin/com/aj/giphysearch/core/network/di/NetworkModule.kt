package com.aj.giphysearch.core.network.di

import com.aj.giphysearch.core.network.HttpClientFactory
import org.koin.dsl.module

fun networkModule(apiKey: String, isDebug: Boolean) = module {
    single { HttpClientFactory.create(apiKey, isDebug) }
}
