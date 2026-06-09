---
name: pixijs-scene-particle-container
description: "Use for PixiJS v8 ParticleContainer and Particle: thousands of lightweight sprites, addParticle/removeParticle, particleChildren, dynamicProperties, boundsArea, roundPixels."
license: MIT
---

Use this for very large counts of lightweight sprite-like particles.

## Fast Path

```ts
import { Particle, ParticleContainer, Texture } from 'pixi.js';

const pc = new ParticleContainer({ dynamicProperties: { position: true, rotation: true } });
pc.addParticle(new Particle({ texture: Texture.WHITE, x: 100, y: 100 }));
app.stage.addChild(pc);
```

## Rules

- `ParticleContainer` stores `Particle` instances in `particleChildren`; use `addParticle`, not `addChild`.
- Wrap the `ParticleContainer` in a normal `Container` when it must be grouped with other display objects.
- Enable only the `dynamicProperties` you mutate (`vertex`, `position`, `rotation`, `uvs`, `color`) to keep uploads cheap.
- Use shared textures/atlases and stable object pools.
- Set `boundsArea` when automatic bounds are not useful.
- Choose `Sprite`/`Container` instead when each object needs filters, masks, events, children, or rich per-object features.

## Deep Reads

- Full options, examples, and lifecycle: [references/details.md](references/details.md)
- Scene graph basics: `pixijs-scene-core-concepts`
- Assets and atlases: `pixijs-assets`
- Performance tradeoffs: `pixijs-performance`

## Common Fixes

- `addChild` fails or acts wrong: use `addParticle`.
- Per-particle interactivity required: use normal sprites instead.
- Slow updates: disable dynamic properties that never change.
