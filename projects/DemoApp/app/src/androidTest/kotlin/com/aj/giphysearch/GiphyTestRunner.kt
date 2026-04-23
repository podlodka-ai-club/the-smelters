package com.aj.giphysearch

import android.app.Application
import android.content.Context
import androidx.test.runner.AndroidJUnitRunner
import com.aj.giphysearch.testing.AppTestApp

class GiphyTestRunner : AndroidJUnitRunner() {
    override fun newApplication(
        cl: ClassLoader?,
        className: String?,
        context: Context?,
    ): Application = super.newApplication(cl, AppTestApp::class.java.name, context)
}
