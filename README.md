# MAS
WIP

## Environment

Python 3.11. `requirements.txt` and `requirements-dev.txt` were pinned by
freezing a clean `pip install` on 2026-08-06 (see the header comment in each
file); regenerate the same way if a dependency needs to change, rather than
hand-editing a version number.

```
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

Run the test suite (network-free — everything is built and tested against
`tests/fixtures/`, never live council servers, per `CLAUDE.md`):

```
.venv/bin/python -m pytest -q
```

Run a script as a module, from the repo root, so `src`/`scripts` resolve as
packages without needing `PYTHONPATH`:

```
.venv/bin/python -m scripts.tally_sprint1_coverage
.venv/bin/python -m scripts.verify_section1
```
