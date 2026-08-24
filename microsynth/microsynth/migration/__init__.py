"""
Bridge package for migration functions.

Why this exists:
- The repository has both a package path "microsynth/microsynth/migration/"
  and a module file "microsynth/microsynth/migration.py".
- Python resolves "microsynth.microsynth.migration" to this package.

To keep all bench entry points on:
  bench execute microsynth.microsynth.migration.<function>
we load and re-export all public callables from migration.py.
"""

import importlib.util
from pathlib import Path


def _load_migration_file_module():
	migration_file = Path(__file__).resolve().parents[1] / "migration.py"
	spec = importlib.util.spec_from_file_location(
		"microsynth.microsynth._migration_file",
		migration_file,
	)
	if not spec or not spec.loader:
		raise ImportError(f"Could not load migration module from {migration_file}")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


_migration_file_module = _load_migration_file_module()

# Re-export all public callables so bench execute can resolve them directly.
for _name in dir(_migration_file_module):
	if _name.startswith("_"):
		continue
	_obj = getattr(_migration_file_module, _name)
	if callable(_obj):
		globals()[_name] = _obj
