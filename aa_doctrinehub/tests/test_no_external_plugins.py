"""aa-doctrinehub may only depend on the platform and our own plugins (workspace AGENTS §15)."""

import re
from pathlib import Path

# Apps by others. Fittings is read only through Django's app registry in services/fittings_sync.py
# (an approved exception), never imported.
FORBIDDEN = ("aadiscordbot", "corptools", "fittings", "memberaudit", "structures", "securegroups")

PACKAGE = Path(__file__).resolve().parent.parent
IMPORT = re.compile(r"^\s*(?:from|import)\s+(" + "|".join(FORBIDDEN) + r")\b", re.MULTILINE)


def test_no_imports_from_external_plugins():
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if "tests" in path.parts or "migrations" in path.parts:
            continue
        for match in IMPORT.finditer(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(PACKAGE)}: {match.group(1)}")
    assert not offenders, offenders
