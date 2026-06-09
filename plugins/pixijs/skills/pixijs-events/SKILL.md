---
name: pixijs-events
description: "Use for PixiJS v8 input events: pointer/mouse/touch/wheel, eventMode, FederatedEvent, propagation/capture, hitArea, cursor, drag, interactiveChildren."
license: MIT
---

Use this for pointer, mouse, touch, wheel, hover, click, drag, and hit testing.

## Fast Path

```ts
sprite.eventMode = 'static';
sprite.cursor = 'pointer';
sprite.on('pointertap', () => select(sprite));
```

## Rules

- v8 uses `eventMode`; replace `interactive = true` with `eventMode = 'static'` or `'dynamic'`.
- Use `passive` for parents that should allow interactive descendants but not receive self hits.
- Set `hitArea` for predictable or cheaper hit testing.
- Use capture listeners only when you need ancestor-first handling.
- For drag, store pointer state, use global coordinates, and convert to the target parent space before setting position.
- Disable `interactiveChildren` on containers whose descendants should not be checked.

## Deep Reads

- Full event modes, event types, propagation, drag, wheel, and hit-area examples: [references/details.md](references/details.md)
- Math and coordinate conversion: `pixijs-math`
- Graphics hit testing: `pixijs-scene-graphics`

## Common Fixes

- Handler never fires: set `eventMode`, ensure visible/renderable ancestors, and check `hitArea`.
- Drag jumps: convert global pointer coordinates to the parent coordinate space.
- Too many hit tests: simplify hit areas or disable unused interactive descendants.
