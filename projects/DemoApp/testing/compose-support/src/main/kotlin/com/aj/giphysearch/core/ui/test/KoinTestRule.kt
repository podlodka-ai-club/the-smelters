package com.aj.giphysearch.core.ui.test

import org.junit.rules.TestRule
import org.junit.runner.Description
import org.junit.runners.model.Statement
import org.koin.core.context.startKoin
import org.koin.core.context.stopKoin
import org.koin.core.module.Module

class KoinTestRule(private val modules: List<Module>) : TestRule {
    override fun apply(base: Statement, description: Description): Statement {
        return object : Statement() {
            override fun evaluate() {
                stopKoin() // Ensure a clean state
                startKoin {
                    modules(modules)
                }
                try {
                    base.evaluate()
                } finally {
                    stopKoin()
                }
            }
        }
    }
}
