package com.aj.giphysearch.data.remote

import android.util.Log
import com.aj.giphysearch.domain.exception.RateLimitExceededException
import okhttp3.Interceptor
import okhttp3.Response

/**
 * An OkHttp interceptor that enforces a client-side rate limit to prevent API errors.
 *
 * Maintains a rolling window of request timestamps. If the number of requests in the
 * specified [timeWindowMillis] exceeds the [limit], it blocks further requests and throws
 * a [RateLimitExceededException].
 */
class RateLimitInterceptor : Interceptor {
    private val timestamps = java.util.ArrayDeque<Long>()
    private val limit = 100
    private val timeWindowMillis = 60 * 60 * 1000L // 1 hour

    override fun intercept(chain: Interceptor.Chain): Response {
        val now = System.currentTimeMillis()

        synchronized(timestamps) {
            // Remove timestamps outside the 1-hour window
            while (timestamps.isNotEmpty() && now - timestamps.peekFirst()!! > timeWindowMillis) {
                timestamps.removeFirst()
            }

            if (timestamps.size >= limit) {
                Log.e("RateLimiter", "API rate limit exceeded. Blocked request to: ${chain.request().url}")
                throw RateLimitExceededException()
            }

            timestamps.addLast(now)
        }

        return chain.proceed(chain.request())
    }
}
