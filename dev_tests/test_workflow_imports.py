"""Regression tests for the ways MET_hobo is actually run, exercised via real
subprocesses rather than pytest's own sys.path setup.

These exist because a prior fix looked correct under `pytest` (which manipulates
sys.path itself) but broke the documented legacy workflow
(`cd MET_hobo; python file_manager.py`, and what run_hobo.bat does): hobo_qaqc.py's
`from MET_hobo import __version__` raised ModuleNotFoundError there, since the repo
root isn't on sys.path when running from inside the package directory. See
CHANGELOG.md.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MET_HOBO_DIR = REPO_ROOT / 'MET_hobo'


def _clean_env():
    """No PYTHONPATH, so only the real invocation (cwd, -m) can put MET_hobo
    or the repo root on sys.path -- not leftover state from the test runner."""
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    return env


def test_legacy_cd_met_hobo_workflow():
    """`cd MET_hobo; python file_manager.py` -- the documented legacy invocation
    and what run_hobo.bat does. `--help` exits via argparse before FileHandling()
    is ever instantiated, so this never touches real directories."""
    result = subprocess.run(
        [sys.executable, 'file_manager.py', '--help'],
        cwd=MET_HOBO_DIR, env=_clean_env(),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'usage' in result.stdout.lower()


def test_module_invocation_from_repo_root():
    """`python -m MET_hobo.file_manager` from the repo root."""
    result = subprocess.run(
        [sys.executable, '-m', 'MET_hobo.file_manager', '--help'],
        cwd=REPO_ROOT, env=_clean_env(),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'usage' in result.stdout.lower()


def test_installed_package_import(tmp_path):
    """`from MET_hobo import file_manager` when im_hobo is pip-installed.

    Run from a neutral directory (not the repo, not MET_hobo/) with a clean
    PYTHONPATH, so the only way this can succeed is a real package install.
    Skipped (not failed) when the current interpreter doesn't have im_hobo
    installed as a package -- e.g. an interpreter with the runtime dependencies
    present but no `pip install -e .` run in it.
    """
    import importlib.metadata
    try:
        importlib.metadata.version('im_hobo')
    except importlib.metadata.PackageNotFoundError:
        pytest.skip('im_hobo is not installed in this interpreter (pip install -e . to exercise this check)')

    result = subprocess.run(
        [sys.executable, '-c', 'from MET_hobo import file_manager; print("OK")'],
        cwd=tmp_path, env=_clean_env(),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'OK' in result.stdout


# --- file_path.config resolution (FileHandling._resolve_config_path) -------------
#
# Regression: FileHandling defaulted its config path to '../file_path.config',
# which only resolves when cwd is MET_hobo/ -- `python -m MET_hobo.file_manager`
# from the repo root raised FileNotFoundError. These test the resolution logic
# directly (not through FileHandling() itself, which would create real
# data/proc directories from whatever config it loads), so nothing here touches
# any real directory.

def test_config_resolution_explicit_path():
    """An explicit path always wins, unchanged -- existence isn't checked here;
    a bad explicit path surfaces via load_config's own FileNotFoundError."""
    from MET_hobo.file_manager import FileHandling
    resolved = FileHandling._resolve_config_path('/some/explicit/file_path.config')
    assert str(resolved) == '/some/explicit/file_path.config'


def test_config_resolution_env_var(tmp_path, monkeypatch):
    """IM_HOBO_CONFIG is used when no explicit path is given."""
    from MET_hobo.file_manager import FileHandling
    config_file = tmp_path / 'env_file_path.config'
    config_file.write_text('dir_source_files = "x"\n')
    monkeypatch.setenv('IM_HOBO_CONFIG', str(config_file))
    monkeypatch.chdir(tmp_path.parent)  # cwd has no file_path.config of its own

    resolved = FileHandling._resolve_config_path(None)
    assert Path(resolved) == config_file


def test_config_resolution_cwd(tmp_path, monkeypatch):
    """file_path.config in the current directory is used when there's no
    explicit path or env var."""
    from MET_hobo.file_manager import FileHandling
    monkeypatch.delenv('IM_HOBO_CONFIG', raising=False)
    config_file = tmp_path / 'file_path.config'
    config_file.write_text('dir_source_files = "x"\n')
    monkeypatch.chdir(tmp_path)

    resolved = FileHandling._resolve_config_path(None)
    assert Path(resolved) == config_file


def test_config_resolution_falls_back_to_repo_root(tmp_path, monkeypatch):
    """With no explicit path, no env var, and no file_path.config in cwd, falls
    back to the repo root -- this is what makes `cd MET_hobo; python
    file_manager.py` keep finding it. Only checks the resolved path, doesn't
    load or touch the real file.

    Uses a fake repo root (module `__file__` monkeypatched, same technique as
    test_config_resolution_raises_clear_error_when_nothing_found below) with a
    real temp file_path.config in it, rather than asserting against the actual
    REPO_ROOT. Asserting against REPO_ROOT only passes where a real
    file_path.config happens to already exist there -- true on a dev machine
    with one set up, false on a clean CI checkout, which can't verify the
    fallback *resolves* to repo-root without a file there to find.
    """
    import MET_hobo.file_manager as file_manager_module
    from MET_hobo.file_manager import FileHandling

    monkeypatch.delenv('IM_HOBO_CONFIG', raising=False)
    cwd_dir = tmp_path / 'cwd'
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)  # empty dir -- no file_path.config here

    fake_repo_root = tmp_path / 'fake_repo'
    fake_config = fake_repo_root / 'file_path.config'
    fake_config.parent.mkdir(parents=True)
    fake_config.write_text('dir_source_files = "x"\n')
    fake_module_file = fake_repo_root / 'MET_hobo' / 'file_manager.py'
    monkeypatch.setattr(file_manager_module, '__file__', str(fake_module_file))

    resolved = FileHandling._resolve_config_path(None)
    assert Path(resolved) == fake_config


def test_config_resolution_raises_clear_error_when_nothing_found(tmp_path, monkeypatch):
    """When none of the candidates exist, raises FileNotFoundError listing every
    path tried and pointing at file_path.config.example."""
    import MET_hobo.file_manager as file_manager_module
    from MET_hobo.file_manager import FileHandling

    monkeypatch.delenv('IM_HOBO_CONFIG', raising=False)
    monkeypatch.chdir(tmp_path)  # empty dir -- no file_path.config here
    # Make the repo-root fallback resolve to this empty tmp_path too, so neither
    # candidate exists (the real repo root does have a file_path.config).
    fake_module_file = tmp_path / 'fake_repo' / 'MET_hobo' / 'file_manager.py'
    monkeypatch.setattr(file_manager_module, '__file__', str(fake_module_file))

    with pytest.raises(FileNotFoundError, match='No file_path.config found') as exc_info:
        FileHandling._resolve_config_path(None)
    message = str(exc_info.value)
    assert str(tmp_path / 'file_path.config') in message
    assert str(tmp_path / 'fake_repo' / 'file_path.config') in message
    assert 'file_path.config.example' in message


# --- dedupe output path resolution (hobo_date_summary.build_dedupe_output_path) --
#
# Renamed from the hardcoded build_bulk_clean_2_path (always Path(source_dir).parent
# / 'bulk_clean_2') to a configurable, source-dir-derived default. Both checks only
# inspect the returned Path -- no directories are created.

def test_dedupe_output_path_configured_wins(tmp_path):
    """An explicit `configured` path always wins, regardless of source_dir."""
    from MET_hobo.hobo_date_summary import build_dedupe_output_path
    configured = tmp_path / 'elsewhere' / 'dedupe_output'
    resolved = build_dedupe_output_path(tmp_path / 'bulk_clean', configured=configured)
    assert resolved == configured
    assert not resolved.exists()


def test_dedupe_output_path_default_derives_from_source_dir_name(tmp_path):
    """With no configured override, defaults to a sibling directory named
    '<source_dir name>_dedup'."""
    from MET_hobo.hobo_date_summary import build_dedupe_output_path
    source_dir = tmp_path / 'bulk_clean'
    resolved = build_dedupe_output_path(source_dir)
    assert resolved == tmp_path / 'bulk_clean_dedup'
    assert not resolved.exists()
