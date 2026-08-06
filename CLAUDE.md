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
- Never hardcode an expected value in verification code. If you are measuring
  something, derive it. Code written to produce an expected number is not a
  measurement.
- Read a dataclass or schema before writing code against it. Never guess an
  attribute name or use hasattr to hedge between two guesses.
- Never install packages ad hoc. Install only from requirements.txt and
  requirements-dev.txt. If something is missing, add it to the correct file.
- Reuse what exists. con29_registry.py has top_level_groups() and by_bucket();
  scripts/tally_sprint1_coverage.py already derives reachability from adapters.
  Do not reimplement with regex.
- Build and test against tests/fixtures/discovery/. Do not make live calls to
  council servers during development.
- Pipelines mask exit codes. Use set -o pipefail or drop the pipe.
- Show me your plan before implementing. One work package at a time.
- Never create a venv outside the repo. Never use /tmp for anything durable.
- Use `python -m package.module` for imports. If you need PYTHONPATH to make an
  import work, the invocation is wrong.