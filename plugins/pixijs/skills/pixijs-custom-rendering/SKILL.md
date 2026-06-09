---
name: pixijs-custom-rendering
description: "Use for PixiJS v8 custom rendering: Shader.from, GlProgram/GpuProgram, UniformGroup typed uniforms, textures as resources, custom Filter, batchers, WebGL/WebGPU shader code."
license: MIT
---

Use this for custom shaders, filters, uniforms, GPU resources, or renderer extensions.

## Rules

- Build shaders with `Shader.from({ gl, gpu, resources })` when supporting WebGL and WebGPU.
- Use `GlProgram` / `GpuProgram` for backend-specific code.
- Uniforms need explicit types in v8: `new UniformGroup({ uTime: { value: 0, type: 'f32' } })`.
- Textures are resources, not scalar uniforms. Pass texture/source/sampler resources at the shader resource level.
- Use `Filter.from(...)` for custom filter pipelines; use custom renderers/batchers only when filters or meshes are not enough.
- Keep shader code synchronized with renderer backend assumptions.

## Deep Reads

- Full shader, filter, and batcher examples: [references/details.md](references/details.md)
- Uniform type table: [references/uniform-types.md](references/uniform-types.md)
- Filter effects: `pixijs-filters`
- Performance and batching: `pixijs-performance`

## Common Fixes

- Old `new Shader(...)` shape: migrate to `Shader.from` options.
- Uniforms silently fail: wrap values with `{ value, type }`.
- Texture uniform fails: move texture resources out of `UniformGroup`.
