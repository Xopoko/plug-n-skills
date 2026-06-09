# Design Intelligence

Design Intelligence is a Codex plugin pack for product and UX judgment. It helps evaluate and improve products, interfaces, flows, and design systems without centering design-tool operation, Figma workflows, CSS implementation, or visual polish alone.

Core stance:

- Start from user needs, product outcomes, and evidence.
- Treat UI as technology-agnostic task, content, state, feedback, recovery, access, and trust design.
- Treat accessibility, usability, and ethical UX as quality floors.
- Separate product framing, information architecture, interaction design, visual communication, and system governance.
- Cover common UI surfaces such as forms, data views, search/browse, onboarding, permissions, notifications, empty/error states, settings, and transactions.
- Prefer validated contracts, scorecards, and evidence-tied recommendations over taste-based critique.
- Do not claim accessibility compliance from screenshots or static review alone.

The router skill is `design-intelligence`. Focused skills:

- `product-framing`
- `interface-architecture`
- `interaction-design`
- `usability-accessibility-review`
- `visual-communication`
- `design-system-governance`

References:

- `references/scorecards.md` defines review severity, lenses, and output shape.
- `references/contracts.md` defines the review and durable decision JSON contracts, including optional UI surface and pattern-obligation fields.

Validation:

```bash
python3 scripts/validate_design_intelligence.py <review-output.json>
```
