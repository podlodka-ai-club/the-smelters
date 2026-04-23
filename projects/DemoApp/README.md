# GiphySearch

Android application that allows users to search and view trending GIFs using the Giphy API.

## Setup Instructions

This project requires a Giphy API Key to run. For security reasons, the API key is not committed to the repository.

1. Create a `local.properties` file in the root directory of the project if it doesn't exist.
2. Add your Giphy API key to the file as follows:
   ```properties
   GIPHY_API_KEY=your_api_key_here
   ```
3. Build and run the project.

## Architecture & Features

* Kotlin & Coroutines
* Jetpack Compose for UI
* Clean Architecture (Domain / Data / UI layers)
* Koin for Dependency Injection
* Paging 3 for pagination
* Coil 3 for GIF loading
* Ktorfit for networking

## Rate Limiting

The application enforces a client-side rate limiter that allows a maximum of 100 requests per hour,
matching the non-production Giphy API key constraints. If the limit is exceeded, the app maps the
failure to a domain rate-limit error and displays a Toast warning the user to wait before making
further requests.
