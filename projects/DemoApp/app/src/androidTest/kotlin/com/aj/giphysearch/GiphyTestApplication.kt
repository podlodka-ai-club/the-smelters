package com.aj.giphysearch

import android.app.Application
import coil3.ImageLoader
import coil3.PlatformContext
import coil3.SingletonImageLoader
import org.koin.android.ext.koin.androidContext
import org.koin.core.context.startKoin

/**
 * Test Application that starts Koin with [testAppModule] instead of the
 * production [appModule], so all ViewModels get [FakeGifRepository] and
 * no real network calls are made during UI tests.
 */
class GiphyTestApplication : Application(), SingletonImageLoader.Factory {

    override fun onCreate() {
        super.onCreate()
        startKoin {
            androidContext(this@GiphyTestApplication)
            modules(testAppModule)
        }
    }

    override fun newImageLoader(context: PlatformContext): ImageLoader =
        ImageLoader.Builder(context).build()
}
