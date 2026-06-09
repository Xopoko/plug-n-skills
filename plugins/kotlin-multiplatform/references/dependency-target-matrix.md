# Dependency Target Matrix

Before adding a dependency, fill this mentally or in notes:

| Dependency | Intended source set | Android | iOS device | iOS simulator | Desktop/JVM | Web/Wasm | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Example | `commonMain` | yes | yes | yes | yes | no | official docs or Maven metadata |

Rules:

- If any configured target is unsupported, do not put it in `commonMain`.
- If the library has platform-specific artifacts, put each artifact in the matching source set.
- Prefer project-owned facades around libraries that may be swapped or platform-specific.
- Verify APIs after major version upgrades.
