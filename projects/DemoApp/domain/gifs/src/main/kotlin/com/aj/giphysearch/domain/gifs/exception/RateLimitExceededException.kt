package com.aj.giphysearch.domain.gifs.exception

import java.io.IOException

class RateLimitExceededException : IOException(
    "Rate limit of 100 requests per hour exceeded. Please wait to make more requests.",
)
