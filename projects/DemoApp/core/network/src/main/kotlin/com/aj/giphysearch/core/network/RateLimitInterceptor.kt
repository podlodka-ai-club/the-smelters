package com.aj.giphysearch.core.network

import okhttp3.Interceptor
import okhttp3.Response
import java.io.IOException

class RateLimitExceededException : IOException(
    "Rate limit of 100 requests per hour exceeded. Please wait to make more requests.",
)

class RateLimitInterceptor : Interceptor {
    private val timestamps = java.util.ArrayDeque<Long>()
    private val limit = 100
    private val timeWindowMillis = 60 * 60 * 1000L // 1 hour

    override fun intercept(chain: Interceptor.Chain): Response {
        val now = System.currentTimeMillis()

        synchronized(timestamps) {
            while (timestamps.isNotEmpty() && now - timestamps.peekFirst()!! > timeWindowMillis) {
                timestamps.removeFirst()
            }

            if (timestamps.size >= limit) {
                throw RateLimitExceededException()
            }

            timestamps.addLast(now)
        }

        return chain.proceed(chain.request())
    }
}
