plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
    alias(libs.plugins.ktorfit)
}

android {
    namespace = "com.aj.giphysearch.data.gifs"
}

dependencies {
    implementation(project(":domain:gifs"))
    implementation(project(":core:network"))

    implementation(libs.ktor.client.core)
    implementation(libs.ktorfit.lib)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.core)
    implementation(libs.koin.core)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(project(":testing:gifs"))
}
