package com.aj.giphysearch.core.network

import java.io.IOException

class RateLimitExceededException : IOException(
    "Rate limit of 100 requests per hour exceeded. Please wait to make more requests.",
)
