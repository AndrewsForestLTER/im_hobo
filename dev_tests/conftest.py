import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
# MET_hobo/ itself, so tests can `import hobo_qaqc`/`file_manager` bare, matching
# the legacy `cd MET_hobo; python file_manager.py` invocation these tests exercise.
sys.path.insert(0, str(_repo_root / 'MET_hobo'))
# The repo root, so `from MET_hobo import ...` (used internally by hobo_qaqc.py,
# file_manager.py, etc.) resolves regardless of how pytest itself was invoked --
# don't rely on `python -m pytest`'s incidental cwd-on-sys.path side effect.
sys.path.insert(0, str(_repo_root))
