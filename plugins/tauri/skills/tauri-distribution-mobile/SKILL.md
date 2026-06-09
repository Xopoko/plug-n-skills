---
name: tauri-distribution-mobile
description: Package, sign, notarize, update, release, or validate Tauri 2 desktop/mobile builds, including bundle targets, updater signatures, macOS/Windows/Linux distribution, Android/iOS setup, CI release checks, and store-readiness planning.
---

# Tauri Distribution And Mobile

Use this skill for release-facing Tauri 2 work: `tauri build`, installers,
updater, code signing, notarization, mobile targets, CI release workflows, and
store-readiness checks.

## Approval Gates

Do not run or mutate these without explicit user approval:

- signing key generation or rotation;
- Apple/Windows/Android signing setup;
- notarization or store upload;
- updater private-key handling;
- release creation, external push, or CI secret changes;
- mobile SDK installation or global toolchain installs.

Never print or commit secrets, certificates, private keys, provisioning
profiles, `.env` values, or updater private keys.

## Build Readiness

Before packaging, verify:

- clean or intentional git diff;
- `productName`, `identifier`, `version`, icons, bundle targets;
- `build.frontendDist` contains built static assets;
- capabilities are least-privilege and match window labels;
- Rust and frontend tests relevant to the release path pass;
- no secrets are staged.

Common local build forms:

```bash
pnpm tauri build
npm run tauri build
yarn tauri build
bun tauri build
deno task tauri build
cargo tauri build
```

Use project-local scripts.

## Updater

Tauri updater requires signed updates. When enabling it:

1. Add Rust and JS updater plugin surfaces.
2. Configure endpoints and public key.
3. Keep the private signing key outside the repository.
4. Add required capability permissions.
5. Test with local/staging endpoints before production rollout.

## Mobile

Android checks:

- Android Studio/SDK/NDK/Java/Gradle are configured.
- Rust Android targets are installed.
- generated Android project exists after `tauri android init`.
- native permissions and plugin mobile code are configured.

iOS checks:

- full Xcode is installed on macOS;
- iOS Rust targets and CocoaPods are available when required;
- bundle id, team, provisioning, entitlements, and signing are explicit;
- generated Apple/iOS project state exists after init.

## Proof

For release work, report exact artifact paths, signing/notarization status,
updater signature status, target platforms, and which launch/build checks were
actually run.
