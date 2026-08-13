# Plugin Icon System

Use this contract for marketplace plugin icons authored through Capability
Workbench. The portfolio should look related, but each icon must first say what
the plugin does. A shared visual style is not a substitute for a semantic mark.

## Semantic Skeleton

Start from a concrete skeleton before writing an image prompt:

1. **One literal hero:** one recognizable object or domain artifact that carries
   the meaning (for example a workbench, compass, drafting compass, controller,
   blueprint, microscope, or scrub brush).
2. **Zero or one support cue:** one subordinate object, notch, path, sheet, or
   badge that clarifies the action. It must not compete with the hero.
3. **One silhouette:** hero and support cue must merge into one thumbnail-scale
   read. Do not compose a scene or a collection of tools.

For first-party plugins, begin with the concrete portfolio catalog in
`prepare_plugin_icon_prompt.py`. Do not derive a generic abstract motif from the
plugin name alone. Unknown plugins receive a deterministic literal-object
fallback, which is a starting hypothesis to review against the description.

## Canonical Artifact

- Generate `assets/icon.png` as a 1024x1024, 8-bit, opaque RGB PNG.
- Use a full-bleed background. Keep meaningful content inside the central 72%
  with at most 8% optical overshoot.
- Use one dominant foreground color and no more than two accents. Meaningful
  adjacent colors need at least 3:1 non-text contrast.
- Keep `interface.composerIcon` and `interface.logo` identical and point both to
  the same `./assets/...` PNG. Declare `interface.brandColor` as `#RRGGBB`.
- Store `assets/icon-prompt.json` when the icon is generated or materially
  redesigned. New prompt contracts use
  `capability_workbench.plugin_icon_prompt.v2`.
- Do not default to SVG, text, initials, screenshots, photos, UI replicas,
  mascots, thin-line illustrations, decorative texture, or object collages.

## Size Gates

Review the exact final bitmap at all four sizes, not only on the 1024 source:

| Size | Gate |
| --- | --- |
| 64x64 | Hero, action, and support relationship are immediately readable. |
| 32x32 | The hero remains recognizable and the support cue stays subordinate. |
| 24x24 | The silhouette does not split into unrelated blobs or close critical gaps. |
| 16x16 | One stable mass remains; fine accents may disappear without changing meaning. |

Reject the icon if recognition depends on reading text, counting tiny parts,
seeing a gradient, or knowing the plugin name. The bundled validator reports
quantized color and luminance-span statistics for 16/24/32/64 simulations; those
are mechanical anti-flatness checks, not proof of semantic readability.

## Silhouette And Collision Review

Use a monochrome silhouette pass at 64, 32, 24, and 16 pixels:

- the hero must remain one connected visual idea;
- the support cue must not become a second equal-weight icon;
- negative spaces needed for recognition must remain open at 24 pixels;
- the outer contour must differ from adjacent portfolio icons;
- compare the icon with every catalog peer that uses the same object class;
- record likely collisions in `collision_avoid` (for example controller vs.
  media play, blueprint vs. generic document, scrub brush vs. paint tool).

Collision review is semantic and manual. Pixel hashes and color histograms can
detect duplicates or flat output, but cannot establish distinct meaning.

## Brand, Trademark, And License Provenance

Every v2 prompt declares `brand_source` even when no third-party brand is used:

- `type`: `original-domain-metaphor`, `brand-adjacent`, or `authorized-brand`;
- `source`: the referenced product/vendor or `none`;
- `trademark_status`: why the direction avoids, permits, or reproduces marks;
- `license`: the asset/license basis or `original-generated-artwork`;
- `authorization`: evidence or `not-required-no-brand-mark`.

Brand-adjacent plugins may use a domain object and compatible mood, but must not
reconstruct a proprietary logo, mascot, distinctive trade dress, or lettermark.
Use an actual brand mark only with a recorded source, license, and authorization.
Generation output does not grant trademark or copyright permission.

## Prompt Workflow

Prepare a catalog-first schema-v2 contract:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/prepare_plugin_icon_prompt.py" <plugin-name> \
  --description "<short plugin purpose>" \
  --json \
  --out plugins/<plugin-name>/assets/icon-prompt.json
```

Override catalog semantics only when the plugin contract requires it:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/prepare_plugin_icon_prompt.py" <plugin-name> \
  --hero "a literal drafting compass" \
  --hero-meaning "architecture inspection" \
  --support-cue "one load-bearing arch" \
  --collision-avoid "generic navigation compass" \
  --json
```

Use the built-in `$imagegen` skill with the emitted `prompt`, save the selected
bitmap as `assets/icon.png`, then wire it:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/wire_plugin_icon.py" plugins/<plugin-name> \
  --icon-path assets/icon.png \
  --brand-color <brandColor from icon-prompt.json>
```

Validate the icon contract independently or through plugin validation:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/validate_plugin_icons.py" plugins/<plugin-name> --require-prompt
python3 "$PLUGIN_ROOT/scripts/plugin/validate_plugin.py" plugins/<plugin-name>
```

When image generation is unavailable, accept a user-supplied licensed asset or
record the missing-icon gap and continue plugin delivery. Do not introduce an
API key, paid service, network dependency, or machine-local generator into the
default path.

## Final Human Gate

Before handoff, confirm:

- one literal hero and no more than one support cue;
- manual 16/24/32/64 semantic and silhouette gates passed;
- no confusing collision with another portfolio icon;
- no text, watermark, private identifier, screenshot, or copied brand asset;
- `brand_source` is accurate and any authorization evidence exists;
- manifest path parity and brand color match the final prompt contract;
- deterministic icon and plugin validators pass.
