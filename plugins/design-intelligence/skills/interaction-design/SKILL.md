---
name: interaction-design
description: "Design or critique flows, task sequences, affordances, feedback, states, error prevention, recovery, undo, progressive disclosure, input burden, keyboard/touch behavior, and interaction psychology."
---

# Interaction Design

Use when the question is what users do, what the system does in response, and how the flow behaves over time. Interaction design is a contract among intent, behavior, feedback, state, and recovery; it is not button styling.

## Interaction Loop

For each task, map:

1. Intent: what the user wants now.
2. Cue: how the action is discoverable.
3. Action: input performed.
4. Feedback: immediate change.
5. State: what is now true.
6. Recovery: mistake/failure handling.
7. Closure: completion signal.

## Cognitive Walkthrough

For important steps, ask:

1. Will the user try to achieve the right effect?
2. Will the user notice the correct action?
3. Will the user connect the action with the intended effect?
4. Will the user see progress after acting?

One "no" is a hesitation. Two or more is likely task failure.

## State Coverage

Do not call an interaction designed until these states have a position:

- default, hover/pointer affordance when relevant, keyboard focus, active/pressed, selected/current;
- disabled with reason, loading, empty, validation error, system error;
- partial success, success/confirmation, and undo/cancellation when applicable.

## Common Pattern Obligations

Check common UI surfaces without assuming a specific toolkit:

- Forms: label and instruction clarity, input burden, defaults, validation timing, error repair, saved progress, review before irreversible submit, and redundant-entry avoidance.
- Search and filters: query feedback, filter chips or equivalent state visibility, sort meaning, empty/no-results recovery, clear/reset path, and saved or shared state when relevant.
- Data actions: selection state, bulk action preview, permission boundaries, destructive-action prevention, undo or confirmation, and post-action status.
- Onboarding, permissions, and consent: timing, value explanation, skip path, denial recovery, privacy expectation, and first-task handoff.
- Notifications and progress: user-controllable urgency, source, timestamp, read/unread state, channel handoff, retry/escalation, and quiet failure handling.
- Asynchronous work: optimistic state, loading duration, cancellation, retry, partial success, conflict resolution, and final closure.

## Heuristics

Use:

- visibility of system status;
- match to user language and mental model;
- user control and freedom;
- error prevention before error messaging;
- recognition over recall;
- flexibility for expert users without punishing novices;
- closure after sequences;
- target size, reachability, and motor accessibility;
- progressive disclosure to reduce cognitive load;
- Hick's Law for choice complexity;
- Fitts's Law for target acquisition.

When adopting a platform/APG/design-system pattern, preserve expected states, keyboard/touch behavior, feedback, and recovery path, not only layout.

## Output

Produce:

1. **Flow model**: entry, steps, decision points, exit.
2. **Friction points**: what users may miss, misunderstand, or fail.
3. **State model**: required states and missing states.
4. **Recovery model**: prevent, warn, undo, retry, or escalate.
5. **Efficiency model**: novice path, expert shortcuts, bulk action, defaults.
6. **Recommendation**: concrete changes to sequence, affordance, feedback, and state.

For durable interaction decisions, use `design_intelligence.decision.v1` from `references/contracts.md`.

## Red Flags

- Silent data changes.
- Unclear save state.
- Destructive action without undo/confirmation.
- Preventable validation delayed until submit.
- Flow requires memory from a previous screen.
- Empty/loading/error states treated as implementation details.
- Mobile touch and keyboard paths not both considered.
