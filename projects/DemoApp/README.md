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
* Ktor Client for networking

## Rate Limiting

The application includes a client-side rate limiter configured to allow a maximum of 100 requests per hour,
because non-prod giphy key allows only that much requests. If the limit is exceeded, the app will log the event and
display a Toast warning the user to wait before making further requests.
