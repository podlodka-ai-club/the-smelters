plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.aj.giphysearch.testing.gifs"
}

dependencies {
    implementation(project(":domain:gifs"))
    implementation(libs.kotlinx.coroutines.core)
}
