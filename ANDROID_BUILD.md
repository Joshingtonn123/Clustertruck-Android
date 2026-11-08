# Android APK build

This repository contains a WebView-based Android wrapper for the Clustertruck WebGL launcher.

## Launcher source

- `launcher/index.html` is the launcher source packaged into the Android app.
- The original root `index.html` remains available for browser hosting.
- The APK workflow copies `launcher/index.html` and the repository's `Build/` game files into the Android app assets.

## Build an APK

1. Open the repository's **Actions** tab.
2. Select **Build Android APK**.
3. Press **Run workflow**, or push a change to `launcher/`, `Build/`, or the Android project files.
4. Open the completed workflow run and download the `Clustertruck-Android-debug` artifact.
5. Extract the artifact ZIP to get `app-debug.apk`.

The workflow builds a debug APK. It does not create a signed release APK.

The launcher downloads/caches the bundled game files into WebView browser storage when INSTALL is pressed. Allow sufficient free storage on the device. This is a WebGL game running inside Android WebView, not a native Unity Android port.
