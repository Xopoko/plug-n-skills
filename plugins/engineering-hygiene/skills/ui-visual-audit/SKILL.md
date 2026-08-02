---
name: ui-visual-audit
description: "Skeptical visual QA workflow for rendered UI and screenshots. Use when building, modifying, reviewing, or verifying web/mobile/desktop UI; captures browser, simulator, emulator, or desktop screenshots; compares implementation to a design; or claims a UI feature is visually correct. Forces a second pass for unrelated visual anomalies beyond acceptance criteria: occlusion, clipping, overlap, blank boxes, broken icons, poor contrast, broken spacing/alignment, inconsistent padding or margins, wrong platform controls, mock-looking or domain-implausible data, responsive/i18n text overflow, and accessibility-visible defects."
---

# UI Visual Audit

Avoid task tunnel vision during UI verification. Treat every rendered UI or screenshot as evidence for both the requested task and nearby unintended defects.

## Operating Rule

Do not call UI visually verified after checking only the explicit acceptance criteria. Always perform these passes when a screenshot, browser, simulator, emulator, or desktop app view is available:

1. Primary pass: verify the user-requested scenario or changed feature.
2. Ambient pass: inspect the whole visible frame for unrelated defects, walking the suspicion checklist in `$PLUGIN_ROOT/references/visual-suspicion-checklist.md` (geometry, spacing/alignment, text, controls, data realism, visual style, responsiveness, accessibility-visible).
3. Plausibility pass: compare visible data, icons, and domain objects with product expectations, local design docs, fixtures, or real API/state when available.
4. Evidence pass: cite the screenshot path, viewport/device, state, and what remains unverified.

If capture tooling is missing — no browser driver, simulator, emulator, or screenshot utility — do not silently downgrade to a code-only "verification". Provision the tool via the sibling skill `provisioning-missing-tools` and capture real evidence.

## Inspection Procedure

- First describe the screen neutrally: main regions, visible controls, data/content, empty/loading/error states, and any overlays.
- Walk the image top-to-bottom and left-to-right. Do not stare only at the changed component.
- Explicitly inspect spacing and alignment: compare margins, padding, gutters, row heights, baseline alignment, icon/text spacing, section gaps, and whether any element looks cramped, floating, or accidentally offset.
- Zoom, crop, retake, or inspect the DOM/view hierarchy when small controls, suffix icons, chart labels, or text edges are unclear.
- Use accessibility trees, DOM snapshots, and automated assertions as support, not as a replacement for the visual pass.
- Compare with platform conventions. Treat malformed native controls, password-eye buttons, disclosure chevrons, tab indicators, search fields, focus rings, and system icons as suspicious.
- For domain-specific visuals or data, ask: "Would this look plausible to an experienced user?" If not, verify the source data or compare to a product/design reference before accepting it.
- Treat unexpected solid-color regions, blank squares, masks, broken image placeholders, debug text, lorem ipsum, seed data, frozen skeletons, and values that look unlike real domain data as suspicious until proven intentional.
- Prefer existing visual regression tools when the repo already has them: Playwright screenshots, Storybook/Chromatic, snapshot galleries, golden screenshots, or saved simulator proofs. Review the rendered diff, not only the pass/fail result.

## Handling Anomalies

- Investigate cheaply first: inspect computed styles, layout constraints, view hierarchy, assets, props, mocks/fixtures, API response, or design tokens.
- If domain knowledge is missing, search local docs, assets, fixtures, design references, and prior screenshots first; browse only when the user asked or a current external standard is needed.
- If it may be intentional, label it `questionable` and state the exact visual cue plus what evidence would disprove it.
- Fix anomalies when they are in scope or clearly introduced by the current work. Otherwise report them separately with severity and a concrete next step.
- Do not bury visual concerns under a generic success statement. Separate requested-flow verification from ambient visual findings.

## Output Format

At the end of UI work, include a compact visual audit block when UI/screenshots were inspected:

```markdown
Visual audit:
- Primary task: verified / blocked / not checked, with screenshot or command evidence.
- Ambient pass: no visible unrelated issues found / issues found.
- Suspicious findings: P1/P2/P3, screen region, why it looks wrong, evidence, next action.
- Not checked: viewports, states, devices, locales, or data conditions not covered.
```

If no issues are found, say what screen, viewport/device, and state were actually inspected instead of writing a generic "looks good".
