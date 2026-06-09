---
name: game-design-intelligence
description: "Route source-backed game design work. Use for gameplay systems, core loops, progression, rewards, economies, balance, motivation, retention, onboarding, difficulty, multiplayer, live-service, content cadence, and player psychology. Do not use for engines, graphics, assets, programming, or implementation details."
---

# Game Design Intelligence

Design engaging, balanced, scalable games before implementation. Stay at player-experience, systems, and design-judgment level.

## Spine

Start with the design question:

1. Player fantasy and primary verbs.
2. Target emotion/aesthetic.
3. Repeated loop and mastery path.
4. System interactions that create dynamics, surprise, and meaning.
5. Progression, economy, rewards, and content cadence without coercion.
6. Evidence, assumptions, and disconfirming signals.

Use MDA: diagnose from player feeling/behavior backward; propose mechanics only when they serve the intended dynamics.

## Route

Use the minimum focused skill:

- `gameplay-systems`: core loop, mechanics, verbs, emergence, design-level game feel.
- `progression-economy-balance`: progression, rewards, currencies, sinks/sources, power curves, pacing, dominant strategies.
- `motivation-retention`: psychology, motivation, retention, ethical commercial fit, dark-pattern review.
- `onboarding-difficulty`: FTUE, tutorials, skill ramps, assists, accessibility of challenge, difficulty curves.
- `multiplayer-live-service`: multiplayer/social dynamics, fairness, toxicity prevention, guilds, live ops, seasons, events, battle passes, late game, content portfolio.

If several apply, sequence: `gameplay-systems` -> `motivation-retention` -> `progression-economy-balance` -> `onboarding-difficulty` -> `multiplayer-live-service`.

## Evidence Rules

- Prefer primary or close-primary sources: game designer talks, studio posts, postmortems, GDC pages, academic papers, and observable behavior from successful games.
- Treat Bartle, Yee, SDT, Flow, 4 Keys, MDA, and live-service patterns as lenses, not truths.
- Ground recommendations in any provided game, genre, audience, telemetry, playtest notes, economy table, review quote, or retention concern.
- Name assumptions, disconfirming signals, and what would prove the recommendation wrong.
- Do not infer commercial success from a checklist; require audience fit, capacity, cadence, value perception, and live evidence.

## Hard Boundaries

- Do not choose game engines, write code, design rendering architecture, create art/assets, or specify programming tasks unless explicitly asked outside this plugin.
- Do not optimize for coercive retention, fake scarcity, gambling-like loops, manipulative friction, pay-to-win pressure, or monetization that harms agency.
- Do not overfit to one game; extract the mechanism and test fit against genre, audience, session length, business model, and production capacity.
- Use player psychology to support autonomy, competence, relatedness, mastery, curiosity, expression, and fair challenge, not manipulation.

## Output

For quick advice:

- key design judgment;
- top 3-7 recommendations;
- main risk or assumption;
- next validation step.

For reusable audits, use `../../references/contracts.md` and `../../references/rubrics.md`.
