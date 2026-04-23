package com.aj.giphysearch

import android.app.Application
import coil3.SingletonImageLoader
import com.aj.giphysearch.di.TimberKoinLogger
import com.aj.giphysearch.di.appModule
import com.aj.giphysearch.feature.gif.ui.GiphyImageLoaderFactory
import org.koin.android.ext.koin.androidContext
import org.koin.core.context.startKoin
import org.koin.core.logger.Level
import timber.log.Timber

class GiphyApp : Application(), SingletonImageLoader.Factory by GiphyImageLoaderFactory() {

    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        }
        startKoin {
            logger(TimberKoinLogger(Level.DEBUG))
            androidContext(this@GiphyApp)
            modules(appModule)
        }
    }
}
