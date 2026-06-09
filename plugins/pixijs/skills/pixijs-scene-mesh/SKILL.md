---
name: pixijs-scene-mesh
description: "Use for PixiJS v8 Mesh and custom geometry: MeshGeometry positions/uvs/indices/topology, MeshSimple, MeshPlane, MeshRope, PerspectiveMesh, vertex animation."
license: MIT
---

Use this for textured custom geometry and vertex deformation.

## Route

- Basic custom triangles/quads: [references/mesh.md](references/mesh.md)
- Per-frame vertex animation: [references/mesh-simple.md](references/mesh-simple.md)
- Grid deformation: [references/mesh-plane.md](references/mesh-plane.md)
- Rope/trail effects: [references/mesh-rope.md](references/mesh-rope.md)
- Perspective-like 2D projection: [references/mesh-perspective.md](references/mesh-perspective.md)
- Expanded entrypoint notes: [references/details.md](references/details.md)

## Rules

- Use options-object constructors in v8.
- Use `MeshGeometry` with positions, UVs, indices, and topology when built-ins are not enough.
- Meshes are leaves; group them in `Container` when combining with other objects.
- Keep geometry updates as small and predictable as possible; avoid rebuilding large buffers unnecessarily.
- For shader-driven effects, route to `pixijs-custom-rendering`.

## Common Fixes

- v7 class names: `SimpleMesh` -> `MeshSimple`, `SimplePlane` -> `MeshPlane`, `SimpleRope` -> `MeshRope`.
- Need children on a mesh: wrap in `Container`.
- Texture appears warped: verify UVs and vertex order.
