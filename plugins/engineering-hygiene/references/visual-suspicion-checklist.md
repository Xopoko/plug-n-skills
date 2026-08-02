# Visual Suspicion Checklist

Companion reference for the `ui-visual-audit` skill. Walk every category during the ambient pass; do not stop at the first finding.

- Geometry: overlap, clipping, truncation, offscreen content, bad safe-area/inset handling, z-index mistakes, scroll traps, layout shift.
- Spacing and alignment: inconsistent padding/margins, uneven gutters, mismatched row heights, awkward section gaps, cramped controls, floating labels/icons, baseline drift, and elements that are visibly too close or too far apart.
- Text: unreadable contrast, overflow, awkward ellipsis, wrong locale/date/currency/number format, stale copy, placeholder strings, debug labels.
- Controls: broken icons, hidden affordances, disabled/hover/focus state confusion, tiny hit targets, accidental backgrounds, inconsistent native behavior.
- Data realism: impossible values, mock content in production-like UI, domain visualizations that do not resemble real data, stale loading/error state.
- Visual style: inconsistent radius, typography, color, elevation, nested cards, accidental white/black/transparent rectangles.
- Responsiveness: compact width, large width, dynamic text size, orientation, keyboard-open state, long translations, and empty/overflow states when relevant.
- Accessibility-visible: contrast, non-text indicator contrast, focus visibility, color-only state, and controls whose state is not visually perceivable.
