plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.aj.giphysearch.core.navigation"
}

dependencies {
    implementation(libs.kotlinx.serialization.json)
}
