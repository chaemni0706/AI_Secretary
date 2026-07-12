plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.frontend"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        // flutter_local_notifications 등 최신 플러그인이 요구하는 코어 라이브러리 디슈가링.
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.example.frontend"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        // vosk_flutter_2 가 minSdk 30 을 요구한다. Z플립3 등 대상 기기는 Android 11+ 이라 무방.
        minSdk = maxOf(flutter.minSdkVersion, 30)
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    // 온디바이스 SmolVLM-500M q4f16 ONNX 추론용 런타임(SmolVlmBridge.kt 에서 사용).
    // 모델 weight 는 git/assets 에 넣지 않고 앱 filesDir 에서 로드한다(SMOL_ONDEVICE_STATUS.md 참조).
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.18.0")
}

flutter {
    source = "../.."
}

dependencies {
    // flutter_local_notifications 가 요구하는 코어 라이브러리 디슈가링 런타임.
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}
