# KMP Environment Readiness

Use this only when host setup may be the problem. It does not replace project inspection.

## Signals

- Xcode or simulator tasks fail before project code compiles.
- CocoaPods/Ruby errors appear during iOS integration.
- Android Studio or KMP plugin setup is suspected.
- JDK or Gradle JVM mismatch appears.
- The project builds on CI but not locally.

## Checks

```bash
xcode-select -p
xcodebuild -version
java -version
./gradlew -version
kdoctor -v
kdoctor --all
```

KDoctor is macOS-only and checks OS, JDK/JAVA_HOME, Android Studio plugins, Xcode, Ruby, and CocoaPods. Do not install it or change host tools without explicit user approval.
