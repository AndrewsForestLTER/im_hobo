# Changelog

All notable changes to this project are documented in this file.

## [1.1.0] - 2026-09-04

### Added
- Settings dialog (`MET_hobo/settings_dialog.py`'s `SettingsDialog`) in the HOBO CSV
  Date Summary GUI (`hobo_date_summary.py`), opened from the new "Pipeline" menu's
  "Settings..." item. Reads and writes `file_path.config` in exactly the format
  `FileHandling.load_config`/`_resolve_config_path` expect -- one row per config key
  (the three required directories, `time_step`, `dedupe_mode`, `dir_dedupe_output`,
  `map_fname2dir`, and all seven `toa5_*` keys), each with a short "(?)" tooltip
  pulled from the README/`doc/source/config_file.rst`. Saves to whichever path the
  config was loaded from (explicit > `IM_HOBO_CONFIG` > cwd > repo root, matching
  `FileHandling._resolve_config_path`), or to the repository root if no config
  existed yet -- seeding the dialog from `file_path.config.example` in that case.
  Directory fields get a Browse (`askdirectory`) button. Save warns (without
  blocking) about directories that don't exist, and offers to create the ones the
  pipeline writes to.
- Run button, embedded in the Settings dialog and enabled after a successful Save.
  Runs `FileHandling(config=...).manage()` in a background thread so the GUI stays
  responsive; a scrolled log pane shows the pipeline's stdout/stderr live via a
  thread-safe `after()`-based redirector, and a completion summary (files processed,
  or the exception and traceback on failure) is appended when the thread finishes.
  Run is disabled while a run is in progress and re-enabled on completion or error.
- `FileHandling.manage()` gained an optional `confirm_cb` parameter (default `None`,
  fully backward compatible) so callers can supply a callable(prompt) -> bool in
  place of the two places `file_manager.py` used a blocking console `input()`
  (`dedupe_mode = "prompt"`, and clearing a final storage directory that holds
  unexpected content). The Settings dialog's Run button passes a thread-safe bridge
  that shows a Tk Yes/No `messagebox` instead -- a console prompt from a background
  thread would otherwise hang the GUI forever with no visible cause.
- Every GUI-triggered run writes its full log to a timestamped file, reusing
  `FileHandling.write_log`'s own `logs/` subdirectory of the final storage directory
  (named `gui_run_<timestamp>.log`, distinct from `write_log`'s own
  `hobo_qaqc_<timestamp>.log`) rather than inventing a new location. The saved
  path is shown in the log pane and status bar after each run.
- Help menu item, opening the project's Read the Docs page
  (<https://im-hobo.readthedocs.io>) in the default browser via `webbrowser.open()`,
  falling back to a local `doc/build/html/index.html` or `README.rst` if that
  fails.
- `dev_tests/test_settings.py`: config read/write round-trip (including a
  Windows-style backslash path), the example-seeding fallback when no config
  exists yet, `run_pipeline`'s `FileHandling`/`confirm_cb` wiring (verified against
  a fake `FileHandling`, never touching real directories), and the
  `gui_run_<timestamp>.log` naming/location logic.

### Fixed
- **Bug against the 1.0.0 dedupe feature, unrelated to the Settings/Run/Help work
  above.** `hobo_date_summary.deduplicate_and_write` only knew about `.csv` files:
  a file that survived dedupe (copied unchanged or truncated) left its
  `TOA5/<stem>.dat` and `parquet/<stem>.parquet` siblings (written by
  `hobo_qaqc.py` alongside it in bulk mode) behind in the original
  `dir_final_storage`, never copied into the dedupe output directory. Confirmed
  against real output: `bulk_clean/TOA5` and `bulk_clean/parquet` existed and were
  populated, but `bulk_clean_dedup` had neither subdirectory at all. Fixed with a
  new `_copy_sibling_outputs` helper, called for every CSV written to the dedupe
  output directory (both the "copied unchanged" and "truncated" branches, and the
  error-row copy branch), name-linking each CSV to its siblings by stem the same
  way `file_manager.qaqc_csv` writes them
  (`export_to_toa5`/`export_to_parquet`). A CSV missing one or both siblings
  (e.g. `final_subdirs=True` mode, where TOA5/Parquet are never written) is
  skipped silently rather than erroring. `file_manager._run_dedupe` and
  `hobo_date_summary`'s own manual/GUI dedupe button both call
  `deduplicate_and_write` directly with no separate copying logic of their own, so
  this one fix covers both entry points. Covered by new
  `dev_tests/test_dedupe.py`, using a synthetic `dir_final_storage` with paired
  CSV/TOA5/parquet files across both dedupe branches, plus cases with only one
  sibling present and with neither present.

## [1.0.0] - 2026-09-02

First release published to GitHub (migrated from Bitbucket) and archived on Zenodo.

### Added
- TOA5 and Parquet output (`HOBOdata.export_to_toa5()`, `HOBOdata.export_to_parquet()`). Written
  automatically alongside the existing CSV output whenever `qaqc_csv`/`manage` run in bulk mode
  (`final_subdirs=False`, the default) — no separate flag needed. Not yet supported when routing to
  per-project site directories (`final_subdirs=True`). Output lands in new `TOA5/` and `parquet/`
  subdirectories of the final storage directory. TOA5 header fields (station, logger model, serial,
  table name, etc.) are optional and configurable via new `toa5_*` keys in `file_path.config`. See
  the README's "TOA5 and Parquet Output" section.
- Logger serial number extraction from the HOBOware header, included in CSV/TOA5 output.
- Date summary and deduplication tooling (`hobo_date_summary.py`) for identifying and resolving
  overlapping CSV exports of the same sensor, with an optional GUI.
- `pytest`-based test suite (`dev_tests/`).
- Packaging/publication metadata: `LICENSE` (MIT), `CITATION.cff`, `.zenodo.json`, `pyproject.toml`.

### Changed
- Upgraded supported Python version to 3.11.
- `copy_src_to_wdir` and `copy_processed_to_final_dir` now clear their target directories before
  copying, fixing stale-file accumulation across runs.
- Renamed `dev_tests/dev_test.py` to `dev_tests/dev_scratch.py`. It's a pre-pytest manual test
  harness (not pytest-shaped — a `Tests` class with an `__init__`, so pytest never collected it
  anyway) that depends on local fixture directories/config files not present in the repository and
  calls a pandas `.ix` accessor removed from pandas years ago; it doesn't run as-is. Renaming keeps
  it out of pytest discovery (`dev_scratch.py` doesn't match pytest's `test_*.py`/`*_test.py`
  patterns) without deleting it. The real automated regression tests are
  `dev_tests/test_output_writers.py`.
- Exported CSV headers now stamp the `im_hobo` package version (e.g. `v1.0.0`) instead of an
  internal `hobo_qaqc`-only version number (previously a hardcoded `3.0`, tracked separately from
  the package version). `hobo_qaqc.py` reads `__version__` from `MET_hobo/__init__.py` — the single
  source of truth for the package version — instead of declaring its own.
- Deleted `requirements.txt` and `requirements-dev.txt`; `pyproject.toml` is now the single
  dependency list (`[project.dependencies]` / `[project.optional-dependencies].test`). CI
  (`.github/workflows/tests.yml`) installs with `pip install -e ".[test]"` instead. Local dev
  environment is `.venv/` (not `venv/`) — see `CLAUDE.md`.
- Renamed the dedupe output directory helper from `build_bulk_clean_2_path` (always a hardcoded,
  development-era `bulk_clean_2` sibling of the source directory) to `build_dedupe_output_path`,
  and made it configurable: the default is now `<source dir name>_dedup` (e.g. `bulk_clean` →
  `bulk_clean_dedup`), or an explicit path via the new optional `dir_dedupe_output` key in
  `file_path.config` (absent by default; `file_manager._run_dedupe` passes it through when set).
  `deduplicate_and_write` gained a matching `dedupe_output=None` parameter. Updates every call site
  in `file_manager.py` and `hobo_date_summary.py` (including the GUI's button label and status
  messages, which no longer hardcode the old name). See the README's new "Deduplication (optional)"
  section for the source → `dir_final_storage` → dedupe output flow.

### Fixed
- `extract_sitecode` preserves the MV008 height suffix.
- Dropped rows with invalid/future dates before downstream processing.
- `conda_environment.yaml` was missing `pyarrow`, a required runtime dependency
  (`hobo_qaqc.py` imports it unconditionally for TOA5/Parquet output) — a fresh
  `conda env create -f conda_environment.yaml` followed by running the pipeline raised
  `ModuleNotFoundError: No module named 'pyarrow'`. Confirmed by actually building the
  environment and reproducing the failure, then re-verifying after the fix. Also dropped the
  `pip: [pathlib]` entry — an unnecessary PyPI backport now that Python 3.11 is required
  (`pathlib` has been in the standard library since 3.4). Also capped `pandas<3`/`numpy<3` to
  match `pyproject.toml`'s pip caps — unpinned, conda-forge resolved `pandas` to `3.0.5`, above
  what's actually been tested against; confirmed the caps take effect (resolves to `2.3.3`) and
  everything still imports cleanly by rebuilding the environment again.
- Regression: `cd MET_hobo; python file_manager.py` (the documented legacy workflow, and what
  `run_hobo.bat` does) raised `ModuleNotFoundError` on `hobo_qaqc.py`'s `from MET_hobo import
  __version__` — the repo root isn't on `sys.path` when running from inside the package directory,
  and the try/except relative-import shim introduced when packaging was added never actually
  exercised that workflow. Fixed with the standard script-bootstrap pattern in `file_manager.py` and
  `hobo_date_summary.py` (insert the package's parent directory onto `sys.path` when `__package__`
  is empty, then use plain absolute imports); `hobo_qaqc.py` is never run as a script, so it now just
  does `from MET_hobo import __version__` unconditionally. `dev_tests/conftest.py` also now puts the
  repo root on `sys.path` explicitly, rather than relying on `python -m pytest`'s incidental
  cwd-insertion (`pytest dev_tests/`, without `-m`, was silently depending on that). Covered by
  `dev_tests/test_workflow_imports.py`, which exercises all three real invocation paths via
  subprocess: the legacy `cd MET_hobo` workflow, `python -m MET_hobo.file_manager` from the repo
  root, and `from MET_hobo import file_manager` in a `pip install`ed environment.
- Regression: fixing the above surfaced a second, related cwd bug. `FileHandling` defaulted its
  config path to `'../file_path.config'`, which only resolves when cwd is `MET_hobo/` —
  `python -m MET_hobo.file_manager` from the repo root raised `FileNotFoundError`. `FileHandling`
  now resolves `file_path.config` independent of cwd, in order: an explicit path passed to
  `FileHandling(config=...)` or the new `--config` CLI flag, then the `IM_HOBO_CONFIG` environment
  variable, then the current directory, then the repository root (`FileHandling._resolve_config_path`).
  A clear `FileNotFoundError` listing every path tried (and pointing at `file_path.config.example`)
  is raised only if none of those exist. `hobo_date_summary.py` has no equivalent config-path
  pattern (it's GUI/folder-browser driven, not config-file driven), so nothing to fix there. Covered
  by five new tests in `dev_tests/test_workflow_imports.py` exercising the resolution order directly.

## Earlier history

Versions prior to 1.0.0 (`BetaV0.1_module` through `1.1`) were released on the project's original
Bitbucket repository (`hjandrews/im_hobo`). Note that the git tags `1.0` and `1.1` from that history
**predate the GitHub migration** and are not part of this project's semantic versioning / Zenodo
release sequence — `1.0.0` above is the first version published to GitHub and archived on Zenodo,
not a re-release of the old Bitbucket `1.0` tag. See the README's Release Notes section for a summary
of that history, and `git log` for full detail.
