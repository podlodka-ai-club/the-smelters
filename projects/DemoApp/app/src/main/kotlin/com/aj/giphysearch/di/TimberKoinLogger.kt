package com.aj.giphysearch.di

import org.koin.core.logger.Level
import org.koin.core.logger.Logger
import org.koin.core.logger.MESSAGE
import timber.log.Timber

class TimberKoinLogger(level: Level = Level.DEBUG) : Logger(level) {
    override fun display(level: Level, msg: MESSAGE) {
        val tag = "Koin"
        when (level) {
            Level.DEBUG -> Timber.tag(tag).d(msg)
            Level.INFO -> Timber.tag(tag).i(msg)
            Level.WARNING -> Timber.tag(tag).w(msg)
            Level.ERROR -> Timber.tag(tag).e(msg)
            Level.NONE -> Unit
        }
    }
}
