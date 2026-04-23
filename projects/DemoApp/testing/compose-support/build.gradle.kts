plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.aj.giphysearch.testing.compose.support"
}

dependencies {
    implementation(project(":feature:gif-ui"))
    implementation(libs.coil.compose)
    implementation(libs.koin.android)
    api(libs.junit)
}
