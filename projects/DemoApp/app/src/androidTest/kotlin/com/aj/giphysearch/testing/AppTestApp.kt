package com.aj.giphysearch.testing

import com.aj.giphysearch.common.GiphyTestApp
import org.koin.core.module.Module

class AppTestApp : GiphyTestApp() {
    override fun getTestModules(): List<Module> = listOf(
        appDomainTestModule,
        appFeatureTestModule,
    )
}
