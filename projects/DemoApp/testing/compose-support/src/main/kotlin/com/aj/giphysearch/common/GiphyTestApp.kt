package com.aj.giphysearch.common

import android.app.Application
import coil3.SingletonImageLoader
import com.aj.giphysearch.feature.gif.ui.GiphyImageLoaderFactory
import org.koin.android.ext.koin.androidContext
import org.koin.core.context.startKoin
import org.koin.core.module.Module

open class GiphyTestApp : Application(), SingletonImageLoader.Factory by GiphyImageLoaderFactory() {

    protected open fun getTestModules(): List<Module> = emptyList()

    override fun onCreate() {
        super.onCreate()
        startKoin {
            androidContext(this@GiphyTestApp)
            modules(getTestModules())
        }
    }
}
