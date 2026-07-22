#!/usr/bin/env python3
"""Import Boundary Checker — Phase 8.3

Verifies that critical module isolation rules are enforced:
  - execution/ does NOT import from agents/
  - agents/ does NOT import from execution/
  - proposals/ does NOT import from agents/ directly
  - risk/ does NOT import from agents/

Run:
    python scripts/check_import_boundaries.py
    # or via pytest:
    PYTHONPATH=. pytest tests/security/test_security.py::TestImportBoundaries -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Map: (module_file_glob, forbidden_import_prefix)
BOUNDARY_RULES = [
    # Execution must not import agents (prevents AI from controlling execution)
    ("apps/backend/app/execution/*.py", "from app.agents"),
    ("apps/backend/app/execution/*.py", "import app.agents"),

    # Agents must not import execution (prevents agents from self-executing)
    ("apps/backend/app/agents/*.py", "from app.execution"),
    ("apps/backend/app/agents/*.py", "import app.execution"),

    # Proposals must not import agents directly (use orchestrator via API)
    ("apps/backend/app/proposals/*.py", "from app.agents"),
    ("apps/backend/app/proposals/*.py", "import app.agents"),

    # Risk engine must not import agents (deterministic only)
    ("apps/backend/app/risk/*.py", "from app.agents"),
    ("apps/backend/app/risk/*.py", "import app.agents"),

    # Risk engine must not import proposals (one-way data flow)
    ("apps/backend/app/risk/*.py", "from app.proposals"),
]

repo_root = Path(__file__).parent.parent
violations: list[str] = []

for file_glob, forbidden in BOUNDARY_RULES:
    for filepath in repo_root.glob(file_glob):
        source = filepath.read_text(encoding="utf-8")
        for i, line in enumerate(source.splitlines(), start=1):
            if forbidden in line and not line.strip().startswith("#"):
                violations.append(
                    f"  VIOLATION: {filepath.relative_to(repo_root)}:{i} — '{forbidden}' found"
                )

if violations:
    print("❌ Import Boundary Violations Found:")
    for v in violations:
        print(v)
    print(f"\nTotal: {len(violations)} violation(s)")
    sys.exit(1)
else:
    print(f"✅ Import boundaries OK — {len(BOUNDARY_RULES)} rules checked, 0 violations")
    sys.exit(0)
