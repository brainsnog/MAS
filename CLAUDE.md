# CON29 Automated Search — working rules

Authority: `docs/CON29_BUILD_HANDOFF.md` for current state, defects and work
packages. `docs/CON29_ROADMAP_v2.md` for architecture. Where they conflict,
the handoff wins and says so explicitly.

## Non-negotiable

1. Verify before building. Query a source before writing an adapter for it.
2. Never build against a source listed in Handoff Section 4. Those are access
   governance decisions, not obstacles. Do not spoof user agents, defeat WAF
   challenges, or ignore robots directives. If a task seems to require it, stop
   and ask.
3. Graceful degradation over omission. A blocked source produces an explicit
   `unavailable_reason` stub or a Bucket 3 classification, never a missing field.
4. Never conflate "queried, no record" with "query failed". See DEF-02.
5. Redact credentials from any captured URL before storage. See DEF-04.
6. Flag architecture-affecting discoveries before acting on them.

## Discipline

- One work package at a time. Do not start the next until tests pass.
- Existing tests must keep passing. Current baseline: 59.
- Update the Project Log and Deviation Log at the end of every session.
- Do not reason about the dissertation, word counts, or the presentation.
  This repo is the build only.