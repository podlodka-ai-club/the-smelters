package com.aj.giphysearch.data.remote

import android.util.Log
import com.aj.giphysearch.BuildConfig
import io.ktor.client.HttpClient
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.plugins.logging.LogLevel
import io.ktor.client.plugins.logging.Logger
import io.ktor.client.plugins.logging.Logging
import io.ktor.http.takeFrom
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

object HttpClientFactory {
    private const val TIMEOUT_MILLIS = 3000L

    fun create(): HttpClient = HttpClient(OkHttp) {
        engine {
            addInterceptor(RateLimitInterceptor())
            config {
                connectTimeout(TIMEOUT_MILLIS, java.util.concurrent.TimeUnit.MILLISECONDS)
            }
        }
        defaultRequest {
            url {
                takeFrom("https://api.giphy.com/v1/")
                parameters.append("api_key", BuildConfig.GIPHY_API_KEY)
            }
        }
        install(ContentNegotiation) {
            json(
                Json {
                    ignoreUnknownKeys = true
                    isLenient = true
                },
            )
        }
        install(Logging) {
            logger = object : Logger {
                override fun log(message: String) {
                    Log.d("Ktor", message)
                }
            }
            level = LogLevel.ALL
        }
    }
}
