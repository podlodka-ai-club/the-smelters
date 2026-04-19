package com.aj.giphysearch

import android.app.Application
import android.content.Context
import androidx.test.runner.AndroidJUnitRunner

class GiphyTestRunner : AndroidJUnitRunner() {
    override fun newApplication(
        cl: ClassLoader?,
        className: String?,
        context: Context?,
    ): Application = super.newApplication(cl, GiphyTestApplication::class.java.name, context)
}
