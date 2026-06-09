# Game Design Intelligence Contracts

Use these contracts when game-design output will be reused by tools, backlog items, reviews, design docs, or later agents. Keep the contract separate from prose.

## Design Review Contract

```json
{
  "schema": "game_design_intelligence.design_review.v1",
  "game": {
    "name": "string",
    "genre": "string",
    "audience": "string",
    "platform_context": "string",
    "business_model": "string"
  },
  "design_intent": {
    "player_fantasy": "string",
    "primary_verbs": ["string"],
    "target_emotions": ["string"],
    "session_length": "string"
  },
  "mda": {
    "aesthetics": ["string"],
    "dynamics": ["string"],
    "mechanics": ["string"],
    "mismatches": ["string"]
  },
  "systems": {
    "core_loop": "string",
    "long_loop": "string",
    "meaningful_choices": ["string"],
    "emergence_opportunities": ["string"],
    "dominant_strategy_risks": ["string"]
  },
  "progression_economy_balance": {
    "progression_layers": ["skill", "content", "power", "status", "identity"],
    "reward_roles": ["string"],
    "sources": ["string"],
    "sinks": ["string"],
    "balance_risks": ["string"],
    "tuning_hypotheses": ["string"]
  },
  "motivation_retention": {
    "supported_needs": ["autonomy", "competence", "relatedness", "curiosity", "expression", "mastery", "status"],
    "underserved_needs": ["string"],
    "retention_drivers": ["string"],
    "fatigue_risks": ["string"],
    "dark_pattern_risks": ["string"]
  },
  "onboarding_difficulty": {
    "first_session_path": ["string"],
    "skill_ramp": ["string"],
    "failure_costs": ["string"],
    "assist_options": ["string"],
    "confusion_risks": ["string"]
  },
  "multiplayer_live_service": {
    "interaction_modes": ["string"],
    "social_health_risks": ["string"],
    "content_cadence": ["string"],
    "late_game_loop": "string",
    "catch_up_paths": ["string"]
  },
  "evidence": {
    "sources": ["string"],
    "assumptions": ["string"],
    "disconfirming_signals": ["string"],
    "validation_probes": ["string"]
  },
  "recommendations": [
    {
      "priority": "P0|P1|P2|P3",
      "change": "string",
      "reason": "string",
      "risk": "string",
      "validation": "string"
    }
  ]
}
```

## Economy Balance Contract

```json
{
  "schema": "game_design_intelligence.economy_balance.v1",
  "resources": [
    {
      "name": "string",
      "player_meaning": "string",
      "sources": ["string"],
      "sinks": ["string"],
      "conversion_paths": ["string"],
      "stockpile_risk": "low|medium|high",
      "scarcity_risk": "low|medium|high",
      "segment_stress": ["novice", "expert", "casual", "latecomer", "lapsed", "free", "spender"]
    }
  ],
  "progression": {
    "early_game": "string",
    "mid_game": "string",
    "late_game": "string",
    "catch_up": "string"
  },
  "balance": {
    "power_curve": "string",
    "dominant_strategy_risks": ["string"],
    "meaningless_choice_risks": ["string"],
    "test_ranges": ["string"]
  },
  "ethics": {
    "player_agency_risks": ["string"],
    "dark_pattern_risks": ["string"],
    "reframes": ["string"]
  }
}
```

## Refusal/Reframe Contract

Use this when the request asks for coercive or manipulative retention.

```json
{
  "schema": "game_design_intelligence.safety_reframe.v1",
  "blocked_request": "string",
  "risk_type": "fake_scarcity|pay_to_win|opaque_gambling|sunk_cost_pressure|coercive_streak|artificial_deficit|hostile_social_pressure|other",
  "why_blocked": "string",
  "player_respecting_alternative": "string",
  "validation": "string"
}
```
