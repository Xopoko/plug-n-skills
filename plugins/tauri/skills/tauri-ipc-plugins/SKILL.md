---
name: tauri-ipc-plugins
description: Implement or review Tauri 2 Rust commands, frontend invoke wrappers, events, Channels, custom errors, state, official plugins, or custom Tauri plugins across Rust, JavaScript, permissions, and mobile surfaces.
---

# Tauri IPC And Plugins

Use this skill for the Rust/frontend boundary: `#[tauri::command]`,
`invoke`, events, Channels, plugin commands, plugin permissions, and typed JS
wrappers.

## Command Pattern

Rust:

```rust
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct Request {
    path: String,
}

#[derive(Serialize)]
struct Response {
    ok: bool,
}

#[tauri::command]
fn do_work(request: Request) -> Result<Response, String> {
    Ok(Response { ok: !request.path.is_empty() })
}
```

Register once:

```rust
tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![do_work])
```

Frontend:

```ts
import { invoke } from "@tauri-apps/api/core";

export function doWork(path: string): Promise<{ ok: boolean }> {
  return invoke("do_work", { request: { path } });
}
```

## Rules

- Use serializable request/response structs instead of loose maps.
- Keep TypeScript wrappers typed; do not spread raw `invoke` calls through UI.
- Avoid `unwrap()` and panics in command paths. Return typed/serialized errors.
- Do not pass secrets through the frontend unless the product design requires
  it and the risk is documented.
- Use events for notifications/broadcasts, not as an authorization mechanism.
- Use async commands or background tasks for blocking work.

## Plugin Checklist

For every plugin, verify all surfaces:

- JS package in `package.json`;
- Rust crate in `src-tauri/Cargo.toml`;
- `.plugin(...)` registration in `src-tauri/src/lib.rs`;
- frontend import and typed wrapper;
- capability permissions in `src-tauri/capabilities/*`;
- mobile-specific setup and permission checks when targeting Android/iOS.

Mobile plugins may expose `plugin:<name>|checkPermissions` and
`plugin:<name>|requestPermissions`; check permission state before requesting.

## Verification

Run targeted Rust and frontend tests. Use Tauri API mocks for invoke wrappers
and `cargo test --manifest-path src-tauri/Cargo.toml` for Rust logic. If plugin
permissions changed, run the Tauri shell path too.
