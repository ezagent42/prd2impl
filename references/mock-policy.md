# prd2impl Mock Policy

This reference is consumed by `skill-3-task-gen`, `skill-5-start-task`,
`skill-6-continue-task`, and `skill-8-batch-dispatch`. It defines what
counts as a correct test under the prd2impl pipeline.

Without an explicit policy, subagents ship `MagicMock()` calling methods
that don't exist on real classes — the cdcfdb2 bug class. This document
makes the rules mechanical.

## What MAY be mocked

1. **External SaaS / network boundaries** — Anthropic API, Doubao,
   third-party REST/gRPC services. Stub at the HTTP layer (e.g.
   `httpx.MockTransport`, `aiohttp` mock server, recorded VCR
   cassette), NOT at the client wrapper class.

2. **Subprocess / CLI invocations** — `claude` CLI, `git`, `pytest`
   when the test is meta-testing the pipeline itself. Stub via
   `monkeypatch.setattr(subprocess, "run", ...)` at the boundary.

3. **Clock / time** — `datetime.utcnow`, `time.time`, `asyncio.sleep`
   for deterministic tests. Use `freezegun` or
   `monkeypatch.setattr(module, "datetime", ...)`.

4. **Filesystem at platform boundary** — disk I/O for path-format
   tests where the actual content doesn't matter. Prefer `tmp_path`
   fixture over mocks for content-bearing tests.

5. **Network sockets** — for protocol tests where the SUT is the
   protocol implementation, not the network. Use `aioresponses` or
   `pytest-httpserver` patterns.

## What MUST NOT be mocked

1. **The system under test (SUT) itself** — if a test mocks the
   class it claims to test, the test proves nothing.

2. **Modules in the same Python package as the test** — internal
   collaborators should be real instances. Use dependency injection
   or fixtures to construct them, not mocks. Example: a test of
   `autoservice.gateway.message_router` may mock the Anthropic
   client but MUST NOT mock `autoservice.cc_pool` — they're in the
   same package and the contract between them is what testing is
   about.

3. **Database** — prefer an ephemeral real instance (sqlite for
   tests, testcontainers for postgres/mysql, etc.) over an in-memory
   mock that diverges from real driver behavior. The 5% performance
   cost is worth the 100% behavior fidelity.

4. **The contract under negotiation** — a Yellow task whose
   contract is `Module.Class.method(...)` MUST NOT test by mocking
   `Module.Class`. Test by AST-walking the consumer code (see
   contract test pattern below) and asserting it resolves on the
   real class.

5. **Inter-module protocols inside this repo** — message bus,
   event publisher, internal RPC. These ARE the integration surface
   prd2impl tasks are coordinating around; mocking them defeats the
   point.

## How to mock safely

### Rule 1 — `spec=Class` is mandatory

When using `MagicMock` or `Mock` for ANY production class. Bare
`MagicMock()` lets you call any method, including ones that don't
exist (the cdcfdb2 enabler).

```python
# WRONG — bare MagicMock
pool = MagicMock()
pool.acquire_for_session(...)  # silently returns another MagicMock
                               # production: AttributeError

# RIGHT — spec'd
from autoservice.cc_pool import CCPool
pool = MagicMock(spec=CCPool)
pool.acquire_for_session(...)  # AttributeError immediately at test time
```

`AsyncMock(spec=Class)` for async classes. `spec_set=Class` to also
prevent setting attributes not on the real class.

### Rule 2 — `autospec=True` for `patch()` decorators

```python
# WRONG
@patch("autoservice.cc_pool.CCPool.session_query")
def test_x(mock_query):
    ...  # mock_query accepts any signature

# RIGHT
@patch("autoservice.cc_pool.CCPool.session_query", autospec=True)
def test_x(mock_query):
    ...  # mock_query has the real signature; arity errors fail the test
```

### Rule 3 — Hand-rolled `_FakeX` requires a paired contract test

`MagicMock(spec=)` is sometimes too restrictive (e.g. you need the
fake to maintain state across calls). Hand-rolled fakes are
acceptable, BUT must be paired with a contract test:

- The fake class declares the same method names as the real class.
- A contract test AST-walks both and asserts method names + signatures
  match. See template at
  `skills/skill-12-contract-check/references/ast-walk-template.md`.
- Drift in either side fails the contract test before it ships.

Without the paired contract test, hand-rolled fakes drift silently —
this is exactly how PV2 cdcfdb2 shipped: `_FakePool` defined
`acquire_for_session` (which doesn't exist on real `CCPool`) and 129
unit tests passed for ~14 days while production logged AttributeError.

## Contract test pattern

For every fake-class boundary in `tests/<production-namespace>/`,
ship a paired contract test. Minimal template:

```python
"""Contract test — verifies _FakePool tracks the real CCPool API.
Auto-generated; regenerate via /contract-check --preflight {task_id}.
"""
import inspect
from autoservice.cc_pool import CCPool
from tests.pipeline_v2.test_runner import _FakePool


def test_fake_pool_methods_match_real():
    """Hand-rolled fake must NOT define methods absent from real class."""
    real_methods = {n for n in dir(CCPool) if not n.startswith('_')}
    fake_methods = {n for n in dir(_FakePool) if not n.startswith('_')}
    extras = fake_methods - real_methods
    assert not extras, (
        f"_FakePool defines methods not on real CCPool: {extras}\n"
        f"This is the cdcfdb2 anti-pattern — fake invents a method name, "
        f"production AttributeErrors silently."
    )


def test_fake_pool_signatures_match_real():
    """Each fake method's signature must be compatible with real."""
    for name in dir(_FakePool):
        if name.startswith('_'): continue
        if not callable(getattr(_FakePool, name)): continue
        if not hasattr(CCPool, name): continue
        fake_sig = inspect.signature(getattr(_FakePool, name))
        real_sig = inspect.signature(getattr(CCPool, name))
        # Allow fake to accept **kwargs as an explicit drift catcher;
        # otherwise param names must match.
        accepts_var_kw = any(
            p.kind == p.VAR_KEYWORD for p in fake_sig.parameters.values()
        )
        assert (
            fake_sig.parameters.keys() == real_sig.parameters.keys()
            or accepts_var_kw
        ), (
            f"_FakePool.{name} signature differs from real: "
            f"{fake_sig} vs {real_sig}"
        )
```

For more elaborate variations (AST-walking the consumer to check
actual call sites), see
`skills/skill-12-contract-check/references/ast-walk-template.md`.

## Project-specific overrides

Projects with genuinely different testing constraints (e.g. extensive
external-SaaS reliance, regulated environments where real-DB tests
aren't possible in CI) can override this policy by writing
`{plans_dir}/mock-policy.local.md` extending or relaxing rules.
`skill-3-task-gen` reads the local override if present.

The override may NOT relax Rule 1 (spec= mandatory) or Rule 3
(contract test required for hand-rolled fakes) — those address the
cdcfdb2 bug class universally.

## Why this exists

Audit of AutoService PV2 milestone (commit `cdcfdb2` et al,
2026-05) found:

- 229 instances of unspec'd `MagicMock()` / `AsyncMock()` across 33
  test files.
- Three contract tests in the entire codebase.
- A method that did not exist on the real class (`acquire_for_session`)
  shipped to production for 14 days because the test fake mirrored
  the fictional API.

This policy + contract test pattern + skill-12's `--preflight`
subcommand close the gap.
