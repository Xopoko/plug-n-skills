---
name: provisioning-missing-tools
description: >-
  Missing toolchains are provisioned when absent, outdated, weak, or
  misconfigured commands, SDKs, runtimes, package managers, drivers, CLIs,
  simulators, emulators, or test/profiling utilities block or downgrade
  end-to-end work.
---

# Provisioning Missing Tools

Missing tools are implementation details, not user-facing blockers. When the user has given a goal, especially "do it end to end", autonomously provision the environment needed to finish the work unless there is a real permission, safety, credential, or destructive-change boundary.

## Default Stance

If a task is blocked or materially weakened by missing tooling, install or configure the needed toolchain and continue. Do not stop at "this environment lacks X" when X can reasonably be installed in the current environment.

This applies to:

- SDKs and build tools: Android SDK, Gradle, JDK, Xcode tools, Flutter, Expo, CMake, Ninja.
- CLI utilities and package managers: Homebrew, apt, pip/pipx, npm/npx, pnpm, uv, cargo, go install.
- Test and device tools: emulators, simulators, adb, fastboot, USB/serial tools, vendor CLIs, flashing/profiling/debugging utilities.
- Better replacements: a newer runtime, faster package manager, missing plugin, or dedicated tool when the current workaround is slow or fragile.

The same stance backs the other hygiene gates in this plugin: never skip a verification pass (tests, builds, or the `ui-visual-audit` screenshot evidence) because the tool that would produce the evidence is not installed yet.

## Provisioning Workflow

1. Confirm the blocker with `command -v`, version output, logs, or the failing command.
2. Pick the least surprising install path for the task: project-local first for project dependencies, user-local for reusable CLIs, system/package-manager install when that is the normal route.
3. Prefer official installers, package managers, and pinned project manifests over ad hoc binaries.
4. Install non-interactively when possible, then verify with version output and a minimal smoke command.
5. Continue the original task. The install is a step toward the goal, not the deliverable.

When the existing environment is technically usable but clearly inferior, consider provisioning the better environment instead of repeatedly fighting the weak path. Examples: install the Android SDK instead of skipping Android verification; install Gradle/JDK instead of describing missing build support; install a USB utility or vendor CLI instead of abandoning device testing.

## Boundaries

Ask the user only when the next step truly needs their decision or authorization:

- Credentials, paid accounts, licenses, or vendor terms the agent cannot accept on the user's behalf.
- Admin/root privileges when no user-local or project-local path is practical.
- Destructive system changes, OS upgrades, kernel extensions, firmware changes, device flashing, or actions that could damage hardware.
- Physical-world safety choices not already specified by the user, such as electrical limits for USB-C power/voltage tests.

If one route is blocked by permissions, try a safe alternate route before asking: local binary, user install, container, toolchain manager, portable SDK, or project-local cache.

## Reporting

Keep status concise and evidence-based:

- Say what was missing or weak only when it mattered.
- State what was installed/configured, where, and the verified version or smoke result.
- Separate "installed and verified" from "attempted but blocked".
- Do not present missing tooling as the final answer unless installation is impossible or requires a user-only boundary.
