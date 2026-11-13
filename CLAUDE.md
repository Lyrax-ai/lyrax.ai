# Lyrax Development Instructions

Phase 1 of Lyrax.

## Specification
The source of truth for verification is:
docs/verification-schema.md

It defines four evaluation dimensions.

## Engineering Rules
- Use deterministic scoring wherever possible.
- Use LLM-as-judge only behind an explicit flag.
- Store raw evidence for every evaluation result, not just scores.
- Never change evaluation thresholds without updating the specification first.
- Do not modify credentials or payment code without flagging the change for review.
- Write tests for new functionality.
- Keep agent registration separate from evaluation logic.
- Preserve existing working functionality.
