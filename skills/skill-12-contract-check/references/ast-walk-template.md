# AST Walk Template — Contract Test Generator

This template generates a pytest contract test that AST-walks a
consumer file and asserts every external call resolves to a real
method on the target class with a compatible signature.

Adapted from the `test_runner_pool_contract.py` pattern shipped in
the AutoService repo as a retroactive fix after PV2 commit `cdcfdb2`
("runner.prewarm — call real acquire_sticky, not the non-existent
acquire_for_session"). The retrofit confirmed that pre-shipping
contract verification is the right home for this check; the template
moves it pre-flight, before code ships.

## When to use

- Whenever a task declares a non-empty `must_call_unchanged: [...]`
  list, drop the rendered template into the project's
  `tests/contract/` directory.
- Whenever a hand-rolled `_FakeX` test double exists alongside a real
  class, pair it with this contract test (per
  `references/mock-policy.md`).
- Skill-12 `--preflight {task_id}` will auto-suggest rendering this
  template into the consumer's test directory if no contract test
  exists yet.

## Template

```python
"""Auto-generated contract test for {consumer_module} -> {target_class}.

Verifies every method called on {target_class_short} from
{consumer_relative_path} exists with a compatible signature on the
real class. Intended to fail fast on the cdcfdb2 bug class:
subagent invents a method name, fake test double mirrors it, CI
green, production AttributeError.

Regenerate by running /contract-check --preflight {task_id}.
"""
import ast
import inspect
import pytest
from {target_module} import {target_class_short}

CONSUMER_PATH = "{consumer_relative_path}"
POOL_NAMES = {{ "pool", "self.pool", "_pool" }}  # Customize per consumer


def _calls_to_target(tree):
    """Yield (call_node, method_name) for every call where the
    receiver matches POOL_NAMES."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            attr = node.func
            if isinstance(attr, ast.Attribute):
                value = attr.value
                # `pool.X(...)` form
                if isinstance(value, ast.Name) and value.id in POOL_NAMES:
                    yield node, attr.attr
                # `self.pool.X(...)` form
                if (isinstance(value, ast.Attribute)
                        and isinstance(value.value, ast.Name)
                        and value.value.id == "self"
                        and value.attr == "pool"):
                    yield node, attr.attr


def test_consumer_calls_resolve_on_real_class():
    """Every method the consumer calls on the target must exist on
    the real class (not just on a fake test double)."""
    src = open(CONSUMER_PATH).read()
    tree = ast.parse(src)
    real_methods = {{
        name for name in dir({target_class_short})
        if callable(getattr({target_class_short}, name))
        and not name.startswith("_")
    }}
    unresolved = []
    for call_node, method_name in _calls_to_target(tree):
        if method_name not in real_methods:
            unresolved.append((call_node.lineno, method_name))
    assert not unresolved, (
        f"Consumer {{CONSUMER_PATH}} calls non-existent methods on "
        f"{target_class_short}: {{unresolved}}\\n"
        f"Available methods: {{sorted(real_methods)}}"
    )


def test_consumer_callsites_match_signatures():
    """Every callsite's positional/keyword usage must match the real
    method's signature (catches the keyword-only-passed-positionally
    bug class)."""
    src = open(CONSUMER_PATH).read()
    tree = ast.parse(src)
    mismatches = []
    for call_node, method_name in _calls_to_target(tree):
        if not hasattr({target_class_short}, method_name):
            continue  # Caught by the previous test
        real_sig = inspect.signature(getattr({target_class_short}, method_name))
        params = list(real_sig.parameters.values())
        # Drop `self`
        params = [p for p in params if p.name != "self"]
        keyword_only_names = [
            p.name for p in params
            if p.kind == p.KEYWORD_ONLY
        ]
        positional_count = len(call_node.args)
        positional_names_at_callsite = [
            p.name for p in params[:positional_count]
        ]
        for name in positional_names_at_callsite:
            if name in keyword_only_names:
                mismatches.append((
                    call_node.lineno,
                    method_name,
                    f"keyword-only arg '{{name}}' passed positionally"
                ))
        # Detect unknown keyword args
        accepted_keywords = {{ p.name for p in params }}
        accepts_var_kw = any(p.kind == p.VAR_KEYWORD for p in params)
        for kw in call_node.keywords:
            if kw.arg is None:
                continue  # **kwargs spread
            if kw.arg not in accepted_keywords and not accepts_var_kw:
                mismatches.append((
                    call_node.lineno,
                    method_name,
                    f"unknown keyword '{{kw.arg}}'"
                ))
    assert not mismatches, (
        f"Consumer {{CONSUMER_PATH}} signature mismatches: {{mismatches}}"
    )
```

## Customization points

- `target_module`, `target_class_short`, `consumer_relative_path` —
  filled by `--preflight`.
- `POOL_NAMES` — adjust for the receiver-name conventions in your
  project (`pool`, `client`, `engine`, etc.).
- Add more receiver patterns to `_calls_to_target` for nested
  attribute access (e.g. `self._pool_handle.X(...)`).

## Pairing with hand-rolled fakes

When a consumer test uses a hand-rolled fake (e.g. `_FakePool`),
add a third test in the same file:

```python
def test_fake_methods_match_real():
    """The hand-rolled fake must mirror the real class's method names."""
    from tests.path.to.fake_module import _FakePool
    real = {{ n for n in dir({target_class_short}) if not n.startswith("_") }}
    fake = {{ n for n in dir(_FakePool) if not n.startswith("_") }}
    extras = fake - real
    assert not extras, (
        f"_FakePool defines methods not on real {target_class_short}: {{extras}} "
        f"(this is the cdcfdb2 anti-pattern — fake invents a method, "
        f"production AttributeErrors)"
    )
```
