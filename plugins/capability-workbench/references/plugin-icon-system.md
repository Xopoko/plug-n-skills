# Plugin Icon System

Use this reference when Capability Workbench creates or updates a
marketplace-backed plugin that needs a Codex manifest icon. The default path uses
the system `$imagegen` skill to produce a polished bitmap asset, then deterministic
Workbench helpers prepare the prompt and wire the final file into the manifest.
The goal is a coherent portfolio of minimal, stylish, long-range readable icons
while still allowing each plugin to own a distinct background color.

## Research Baseline

- Apple Human Interface Guidelines, App icons: app icons should express one
  memorable idea, stay simple, avoid nonessential text, prefer vector source,
  keep primary content centered, and use a 1024 square source for square app
  icon contexts.
- Apple Human Interface Guidelines, Icons: effective icons express one concept
  and should remain recognizable when small.
- Material Design 3, Designing icons: icon sets need consistent style, live
  area discipline, bold geometric shapes, consistent stroke/visual weight, and
  small-size optical checks.
- Material Design 3, Applying icons: optical size and weight matter because an
  icon should read similarly at dense and larger display sizes.
- WCAG 2.2, Non-text Contrast: meaningful graphical objects need at least 3:1
  contrast against adjacent colors; very thin lines can underperform even when
  nominal colors pass.
- Local plugin icon corpus review: the most readable marketplace icons use one
  large central mark, a distinct but simple background, high foreground
  contrast, and few foreground parts. Text-heavy logos, tiny letters, and
  detailed scenes do not scale well in plugin lists or pickers.

## Portfolio Contract

Canonical output:

- `assets/icon.png` at 1024x1024 is the default marketplace icon artifact.
- `assets/icon-prompt.json` is optional provenance for the imagegen prompt
  contract.
- SVG/vector generation is not the default. Use it only when the user explicitly
  asks for vector output or the target plugin already has a vector logo system.
- `.codex-plugin/plugin.json` should wire `interface.composerIcon` and
  `interface.logo` to the generated icon path.
- `interface.brandColor` should match the icon background base color from the
  prompt contract or final visual.

Canvas and safe area:

- Use a 1024x1024 square canvas.
- Keep the background full bleed and opaque; rounded-corner backgrounds are
  acceptable inside the image, but do not rely on external masking.
- Keep the primary mark centered.
- Keep most meaningful foreground content inside the central 72 percent of the
  canvas. Optical overshoot may enter the next 8 percent when it improves
  balance.

Foreground anatomy:

- Use one primary silhouette or concept.
- Use at most three meaningful foreground groups.
- Use filled geometric forms by default. Thick strokes are acceptable when they
  are part of a bold silhouette.
- Use a consistent visual weight across all generated icons.
- Prefer front-facing, flat symbols. Avoid isometric scenes, screenshots,
  photos, product UI replicas, and decorative texture.
- Avoid visible text, initials, words, tiny badges, and tiny decorative dots as
  the default path. A brand mark with letters is an exception only when the user
  explicitly asks for brand fidelity.

Color:

- Background color may vary per plugin.
- Foreground and meaningful accents must keep at least 3:1 contrast against the
  background and adjacent background gradient stop.
- Use one dominant foreground color plus up to two accent colors.
- Do not rely on hue alone to separate meaningful parts.
- Avoid low-contrast pastel-on-pastel combinations and very thin strokes.

Style boundaries:

- Do not copy proprietary brand marks unless the plugin is for that brand and
  the user or source material authorizes brand use.
- Do not include private project names, local paths, private names, credentials,
  or screenshots in generated icons.
- Do not require network, paid APIs, image-generation services, telemetry, or
  credentials for the default generation path.

## Imagegen Workflow

For new plugin scaffolds, prefer this sequence:

```bash
python3 scripts/plugin/create_basic_plugin.py <plugin-name> \
  --with-skills \
  --with-scripts \
  --with-assets \
  --with-marketplace
```

Prepare the imagegen prompt contract:

```bash
python3 scripts/plugin/prepare_plugin_icon_prompt.py <plugin-name> \
  --description "<short plugin purpose>" \
  --json \
  --out plugins/<plugin-name>/assets/icon-prompt.json
```

Then use the built-in `$imagegen` skill with the `prompt` from
`assets/icon-prompt.json`. Save the selected generated image into the plugin
workspace as:

```text
plugins/<plugin-name>/assets/icon.png
```

Finally wire the existing asset into the Codex manifest:

```bash
python3 scripts/plugin/wire_plugin_icon.py plugins/<plugin-name> \
  --icon-path assets/icon.png \
  --brand-color <brandColor from icon-prompt.json>
```

Use the imagegen built-in tool by default. Do not use API-key, CLI, or native
transparent-background fallback paths unless the user explicitly asks for them
or confirms the fallback required by the system imagegen skill.

## Review Checklist

Before handing off a generated icon:

- Confirm the manifest icon paths point to existing files.
- Confirm the foreground mark is readable at 64x64 and still recognizable at
  32x32.
- Confirm the icon has no visible text unless explicitly required.
- Confirm meaningful foreground colors meet 3:1 contrast against the
  background.
- Confirm the icon does not contain local/private names, screenshots, photos, or
  copied brand assets.
- Run plugin validation from the repository root:

  ```bash
  python3 scripts/validate-repository.py
  ```
