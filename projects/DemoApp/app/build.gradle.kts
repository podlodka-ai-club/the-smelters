import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.aj.giphysearch"

    defaultConfig {
        applicationId = "com.aj.giphysearch"
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "com.aj.giphysearch.GiphyTestRunner"
        val properties = Properties()
        val localPropertiesFile = project.rootProject.file("local.properties")
        if (localPropertiesFile.exists()) {
            properties.load(localPropertiesFile.inputStream())
        }
        val apiKey = properties.getProperty("GIPHY_API_KEY") ?: ""
        buildConfigField("String", "GIPHY_API_KEY", "\"$apiKey\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(project(":domain:gifs"))
    implementation(project(":data:gifs"))
    implementation(project(":core:ui"))
    implementation(project(":core:network"))
    implementation(project(":core:navigation"))
    implementation(project(":feature:gif-ui"))
    implementation(project(":feature:search"))
    implementation(project(":feature:trending"))
    implementation(project(":feature:details"))

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.paging.runtime)
    implementation(libs.androidx.paging.compose)

    implementation(libs.koin.android)
    implementation(libs.koin.androidx.compose)
    implementation(libs.timber)

    implementation(libs.coil.compose)
    implementation(libs.coil.gif)
    implementation(libs.coil.network.okhttp)

    implementation(libs.ktor.client.core)
    implementation(libs.ktor.client.okhttp)
    implementation(libs.ktor.client.content.negotiation)
    implementation(libs.ktor.serialization.kotlinx.json)
    implementation(libs.ktor.client.logging)

    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.core)
    implementation(libs.androidx.profileinstaller)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.turbine)
    testImplementation(libs.androidx.paging.testing)
    testImplementation(project(":testing:gifs"))

    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.material)
    androidTestImplementation(libs.kaspresso)
    androidTestImplementation(libs.kaspresso.compose.support)
    androidTestImplementation(libs.koin.test)
    androidTestImplementation(libs.koin.test.junit4)
    androidTestImplementation(project(":testing:gifs"))
    androidTestImplementation(project(":testing:compose-support"))
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}
