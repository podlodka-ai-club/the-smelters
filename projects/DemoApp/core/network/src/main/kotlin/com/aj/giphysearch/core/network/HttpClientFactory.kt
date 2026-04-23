package com.aj.giphysearch.core.network

import io.ktor.client.HttpClient
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.plugins.api.createClientPlugin
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.plugins.logging.LogLevel
import io.ktor.client.plugins.logging.Logger
import io.ktor.client.plugins.logging.Logging
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json
import okhttp3.Dispatcher
import timber.log.Timber

object HttpClientFactory {
    private const val TIMEOUT_MILLIS = 3000L
    private const val MAX_REQUESTS = 64
    private const val MAX_REQUESTS_PER_HOST = 20

    fun create(apiKey: String, isDebug: Boolean): HttpClient = HttpClient(OkHttp) {
        engine {
            config {
                connectTimeout(TIMEOUT_MILLIS, java.util.concurrent.TimeUnit.MILLISECONDS)
                addInterceptor(RateLimitInterceptor())
                dispatcher(
                    Dispatcher().apply {
                        maxRequests = MAX_REQUESTS
                        maxRequestsPerHost = MAX_REQUESTS_PER_HOST
                    }
                )
            }
        }
        defaultRequest {
            url {
                parameters.append("api_key", apiKey)
            }
        }
        install(
            createClientPlugin("ApiKeyPlugin") {
                onRequest { request, _ ->
                    // Ensure api_key is present after all URL transformations (including Ktorfit-generated URLs).
                    if (request.url.parameters["api_key"].isNullOrBlank()) {
                        request.url.parameters.append("api_key", apiKey)
                    }
                }
            }
        )
        install(ContentNegotiation) {
            json(
                Json {
                    ignoreUnknownKeys = true
                    isLenient = true
                },
            )
        }
        if (isDebug) {
            install(Logging) {
                logger = object : Logger {
                    override fun log(message: String) {
                        Timber.tag("Ktor").d(message)
                    }
                }
                level = LogLevel.ALL
            }
        }
    }
}
