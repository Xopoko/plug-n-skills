---
name: pixijs-ticker
description: "Use for PixiJS v8 Ticker and render loop control: add/addOnce/remove, deltaTime/deltaMS/elapsedMS, UPDATE_PRIORITY, maxFPS/minFPS, speed, shared/private ticker."
license: MIT
---

Use this for per-frame logic, animation timing, ticker priority, and render-loop control.

## Fast Path

```ts
app.ticker.add((ticker) => {
  sprite.x += 120 * (ticker.deltaMS / 1000);
});
```

## Rules

- v8 ticker callbacks receive the `Ticker` object, not a numeric delta as the first argument.
- Use `deltaTime` for 60fps-scaled movement and `deltaMS` / `elapsedMS` for real milliseconds.
- Use `UPDATE_PRIORITY` when update order matters.
- Use `maxFPS`, `minFPS`, and `speed` sparingly and document why.
- Remove callbacks when objects are destroyed; keep function references stable.
- Know whether you are using `app.ticker`, `Ticker.shared`, or a private ticker.

## Deep Reads

- Full ticker lifecycle, priorities, caps, and callback examples: [references/details.md](references/details.md)
- Application ticker plugin: `pixijs-application`
- Performance triage: `pixijs-performance`

## Common Fixes

- Animation speed changed after migration: read `ticker.deltaTime` or `deltaMS` from the callback argument.
- Callback keeps firing after destroy: call `ticker.remove(fn, context)`.
- Double updates: check shared vs private ticker use.
