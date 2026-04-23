import com.android.build.api.dsl.ApplicationExtension
import com.android.build.api.dsl.CommonExtension
import com.android.build.api.dsl.LibraryExtension
import io.gitlab.arturbosch.detekt.Detekt
import io.gitlab.arturbosch.detekt.extensions.DetektExtension
import org.gradle.api.JavaVersion
import org.gradle.api.Project
import org.jetbrains.kotlin.compose.compiler.gradle.ComposeCompilerGradlePluginExtension
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.tasks.KotlinJvmCompile

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.detekt) apply false
}

subprojects {
    apply(plugin = "io.gitlab.arturbosch.detekt")

    pluginManager.withPlugin("com.android.application") {
        configureAndroidDefaults()
        extensions.configure<ApplicationExtension>("android") {
            defaultConfig {
                targetSdk = rootProject.libs.versions.androidTargetSdk.get().toInt()
            }
        }
    }
    pluginManager.withPlugin("com.android.library") {
        configureAndroidDefaults()
        extensions.configure<LibraryExtension>("android") {
            testOptions {
                targetSdk = rootProject.libs.versions.androidTargetSdk.get().toInt()
            }
        }
    }

    pluginManager.withPlugin("org.jetbrains.kotlin.plugin.compose") {
        extensions.configure<ComposeCompilerGradlePluginExtension>("composeCompiler") {
            stabilityConfigurationFiles.add(
                rootProject.layout.projectDirectory.file("config/compose-gif-stability.conf"),
            )
        }
    }

    extensions.configure<DetektExtension>("detekt") {
        toolVersion = rootProject.libs.versions.detekt.get()
        config.setFrom(rootProject.file("config/detekt/detekt.yml"))
        buildUponDefaultConfig = true
        allRules = false
    }

    dependencies {
        add("detektPlugins", rootProject.libs.detekt.formatting)
    }

    tasks.withType<Detekt>().configureEach {
        jvmTarget = rootProject.libs.versions.jvmTarget.get()
        parallel = true
        autoCorrect = true
    }

    tasks.withType<KotlinJvmCompile>().configureEach {
        compilerOptions {
            jvmTarget.set(JvmTarget.fromTarget(rootProject.libs.versions.jvmTarget.get()))
        }
    }
}

fun Project.configureAndroidDefaults() {
    extensions.configure<CommonExtension<*, *, *, *, *, *>>("android") {
        val compileSdkVersion = rootProject.libs.versions.androidCompileSdk.get().toInt()
        val minSdkVersion = rootProject.libs.versions.androidMinSdk.get().toInt()
        val javaVersion = JavaVersion.toVersion(rootProject.libs.versions.javaVersion.get())

        compileSdk = compileSdkVersion

        defaultConfig {
            minSdk = minSdkVersion
        }

        compileOptions {
            sourceCompatibility = javaVersion
            targetCompatibility = javaVersion
        }
    }
}
