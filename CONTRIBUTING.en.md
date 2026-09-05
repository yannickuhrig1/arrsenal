*[Français](CONTRIBUTING.md) · **English***

# Contributing

Thanks for taking a look. This project has one rule that outranks all the others, and it
is worth knowing before you write any code.

## The rule: guess nothing

**Do not guess any API endpoint, any image tag, any port number, any field name, any
version.** Verify against the official documentation or, better, against a real instance.

This is not a pose. During phase 1 alone, five perfectly reasonable assumptions turned out
to be false on first contact with a real container:

| What seemed obvious | What is true |
|---|---|
| Radarr is on 5.x | 6.3.0 |
| `AuthenticationMethod=External` is enough | it leaves the web UIs **with no login** |
| You can set Category *and* Directory | they are mutually exclusive, and a default category is already filled in |
| The Jellyfin notification takes host + port | it requires an API key, which must be created first |
| `forceSave=true` skips validation | it skips nothing, the indexer is contacted regardless |

Each of them would have produced plausible, broken code. They are all recorded with their
HTTP codes in [docs/COMPATIBILITY.en.md](docs/COMPATIBILITY.en.md).

When a fact is not verifiable in your environment, write `TODO(verify)` and say so in the
pull request. A flagged gap is better than an invention.

## Setting up the environment

```bash
git clone <your-fork>
cd plugarr
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

```bash
ruff check src tests scripts
pytest -q
```

The full suite runs **without Docker and without network access**. If a test you add needs
either of them, it belongs to the integration job.

## How the project is split

```
core     catalog, models, layout, seed, compose, wiring, orchestrator, dashboard
         -> no dependency on Typer or Textual, testable without Docker
cli      turns options into calls, renders the events
tui      the same thing from the keyboard
```

**The CLI and the wizard must never contain business logic.** They call
`orchestrator.py`. That is what guarantees they will not drift apart.

## Adding a service

In most cases an entry in `catalog.py` is enough: the wizard, the CLI, the access page and
the summary discover it on their own. You only need to touch the TUI if the service
requires a new kind of interaction.

If the service needs particular wiring, add a step in `wiring.py`. A step must be:

- **idempotent** — check for existence before creating, never overwrite a manual setting;
- **verified** — validated by the target application's *Test* button, not by the POST's
  return code;
- **schema-driven** — ask the application for its template rather than hardcoding JSON, and
  report the fields a version does not expose instead of losing them.

Pin the image tag. A floating tag makes the wiring non-reproducible; a test fails if you
forget.

## Writing tests

A test must say **why** it exists, not only what it checks. Compare:

```python
def test_download_dir():
    assert s["rpc-whitelist-enabled"] is False
```

```python
def test_transmission_settings_allow_container_to_container_rpc():
    # Sans ces deux reglages, Sonarr/Radarr sont refuses par Transmission.
    assert s["rpc-whitelist-enabled"] is False
    assert s["rpc-host-whitelist-enabled"] is False
```

The second one survives a re-read six months later.

## The README screenshots

They are **generated**, not taken by hand:

```bash
python scripts/screenshots.py
```

The script runs without a terminal and without Docker, and produces identical files from
one run to the next. CI fails if the README shows a stale version of the interface:
regenerate and commit.

## The indexer audit

Prowlarr ships more than 600 definitions whose shape changes with every version.
`scripts/audit_indexers.py` runs the credential detection heuristic against all of them, and
**fails if a definition exposes a field in an unexpected shape**.

It runs in CI. If you see it flag a new case: examine it, then add it to the script's
`REVIEWED_*` lists if it is correct, or extend the heuristic if it is not. Do not silence it
without looking.

## Secrets

No key, no password, no token in the repository — including in test fixtures and
screenshots. `.env`, `stack.yml`, `docker-compose.yml` and the access page are generated and
ignored by git; do not commit them.

In the logs, secrets go through `mask()`. Mask on the variable **name**, never on the shape
of the value: a JWT does not look like a hexadecimal key, and pattern-based masking lets it
through.

## Indexers and content

PlugArr provides, hosts and recommends **no indexer, no tracker, no content**. The list the
user sees comes from their own Prowlarr.

Pull requests adding an indexer list, a preconfigured tracker or a recommendation will be
refused. This is not negotiable: it is what protects the project and its users. See
[DISCLAIMER.en.md](DISCLAIMER.en.md).

## Pull requests

- one intent per pull request;
- `ruff check` and `pytest` green;
- the commit message explains **why**, not just what;
- if you verified a behaviour against a real instance, add it to `docs/COMPATIBILITY.md`
  with its version and its return code. It is the most useful document in the repository.
  Write it in whichever of the two languages you are comfortable with; we keep
  `docs/COMPATIBILITY.en.md` in step.

## Language

The code and the comments are in French, and French is the source language for the
documentation: the `.en.md` files are translations kept in step with it. Python
identifiers stay in English, by convention of the language. A pull request in English
will be read and accepted, and we will translate it.
