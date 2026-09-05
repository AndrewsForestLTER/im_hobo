"""Tests for MET_hobo/settings_dialog.py's non-Tk logic: config read/write
round-trip, example-seeding fallback, pipeline-invocation wiring, and log
file naming/location. None of these construct a Tk widget or a real
FileHandling (whose __init__ has directory side effects), so they run
headless and never touch real pipeline directories.
"""
from pathlib import Path

import pytest

from MET_hobo import settings_dialog
from MET_hobo.file_manager import FileHandling


# --- config read/write round-trip -------------------------------------------

def test_write_then_load_round_trip(tmp_path):
    """Values written by write_config_file are read back unchanged by the same
    FileHandling.load_config the pipeline uses -- the dialog must not invent a
    config format of its own."""
    config_path = tmp_path / 'file_path.config'
    values = {
        'dir_source_files': str(tmp_path / 'src'),
        'dir_local_processing': str(tmp_path / 'work'),
        'dir_final_storage': str(tmp_path / 'final'),
        'time_step': '15min',
        'dedupe_mode': 'auto',
        'dir_dedupe_output': str(tmp_path / 'dedup'),
        'map_fname2dir': {'RS': 'REFSTAND', 'TS': 'STREAMT'},
        'toa5_station': 'MS045',
        'toa5_serial': '12345',
    }

    settings_dialog.write_config_file(config_path, values)
    loaded = FileHandling.load_config(config_path)

    assert loaded == values


def test_write_config_omits_blank_optional_keys(tmp_path):
    """Optional keys left blank are omitted entirely, not written as empty
    strings -- matching the documented 'or key absent' semantics for e.g.
    dedupe_mode and dir_dedupe_output."""
    config_path = tmp_path / 'file_path.config'
    values = {
        'dir_source_files': str(tmp_path / 'src'),
        'dir_local_processing': str(tmp_path / 'work'),
        'dir_final_storage': str(tmp_path / 'final'),
        'time_step': '',
        'dedupe_mode': '',
        'dir_dedupe_output': '',
        'map_fname2dir': None,
    }

    settings_dialog.write_config_file(config_path, values)
    loaded = FileHandling.load_config(config_path)

    assert 'dedupe_mode' not in loaded
    assert 'dir_dedupe_output' not in loaded
    assert 'time_step' not in loaded
    assert 'map_fname2dir' not in loaded
    assert loaded['dir_source_files'] == str(tmp_path / 'src')


def test_write_config_preserves_windows_style_paths(tmp_path):
    """A path containing backslashes (as askdirectory can return on Windows,
    and as a user might type) must round-trip through repr()/ast.literal_eval
    without the backslashes being interpreted as escape sequences."""
    config_path = tmp_path / 'file_path.config'
    windows_path = r'D:\Projects\im_hobo\data'
    values = {
        'dir_source_files': windows_path,
        'dir_local_processing': str(tmp_path / 'work'),
        'dir_final_storage': str(tmp_path / 'final'),
    }

    settings_dialog.write_config_file(config_path, values)
    loaded = FileHandling.load_config(config_path)

    assert loaded['dir_source_files'] == windows_path


# --- example-seeding fallback ------------------------------------------------

def test_load_field_values_uses_example_when_config_missing():
    """When the resolved path doesn't exist, load_field_values() falls back to
    the repo's file_path.config.example rather than returning nothing."""
    missing_path = settings_dialog.REPO_ROOT / 'file_path.config.does_not_exist'
    values = settings_dialog.load_field_values(missing_path, exists=False)

    example_values = FileHandling.load_config(
        settings_dialog.REPO_ROOT / 'file_path.config.example')
    assert values == example_values
    assert values['dir_source_files'] == '/path/to/input'


def test_load_field_values_uses_real_config_when_present(tmp_path):
    """When the resolved path does exist, its own values are used -- not the
    example template."""
    config_path = tmp_path / 'file_path.config'
    settings_dialog.write_config_file(config_path, {
        'dir_source_files': str(tmp_path / 'src'),
        'dir_local_processing': str(tmp_path / 'work'),
        'dir_final_storage': str(tmp_path / 'final'),
    })

    values = settings_dialog.load_field_values(config_path, exists=True)
    assert values['dir_source_files'] == str(tmp_path / 'src')


def test_resolve_settings_config_path_falls_back_to_repo_root(monkeypatch):
    """When FileHandling._resolve_config_path finds nothing (no explicit path,
    no env var, no file_path.config in cwd or repo root), the dialog's resolver
    falls back to <repo root>/file_path.config as the save target -- matching
    'Save writes file_path.config to ... repo root if none existed yet.'"""
    def _raise(_config):
        raise FileNotFoundError('No file_path.config found')
    monkeypatch.setattr(FileHandling, '_resolve_config_path', staticmethod(_raise))

    path, exists = settings_dialog.resolve_settings_config_path()
    assert path == settings_dialog.REPO_ROOT / 'file_path.config'
    # Doesn't assert exists is False outright: a real file_path.config may or may
    # not exist at the repo root on a given dev machine (it's gitignored, user-set
    # up). Just check `exists` accurately reflects the real filesystem state,
    # without this test creating or depending on that file itself.
    assert exists == path.exists()


# --- pipeline invocation wiring ----------------------------------------------

class _FakeFileHandling:
    """Stands in for the real FileHandling, which has directory side effects
    in __init__ (mkdir on data_dir/proc_dir). Records how it was constructed
    and run instead of touching any real path."""

    instances = []

    def __init__(self, config=None):
        self.config_arg = config
        self.manage_calls = []
        self.files = {'.csv': ['a.csv', 'b.csv']}
        _FakeFileHandling.instances.append(self)

    def manage(self, **kwargs):
        self.manage_calls.append(kwargs)


def test_run_pipeline_wires_config_path_and_confirm_cb(monkeypatch, tmp_path):
    """run_pipeline() must construct FileHandling(config=<path>) and call
    .manage(confirm_cb=...) with the callback it was given -- without ever
    touching a real directory (FileHandling is swapped for a fake)."""
    _FakeFileHandling.instances.clear()
    monkeypatch.setattr(settings_dialog, 'FileHandling', _FakeFileHandling)

    config_path = tmp_path / 'file_path.config'
    sentinel_cb = lambda prompt: True  # noqa: E731

    handler = settings_dialog.run_pipeline(config_path, confirm_cb=sentinel_cb)

    assert isinstance(handler, _FakeFileHandling)
    assert handler.config_arg == str(config_path)
    assert handler.manage_calls == [{'confirm_cb': sentinel_cb}]
    assert not config_path.exists()  # run_pipeline itself created no files


def test_run_pipeline_defaults_confirm_cb_to_none(monkeypatch, tmp_path):
    _FakeFileHandling.instances.clear()
    monkeypatch.setattr(settings_dialog, 'FileHandling', _FakeFileHandling)

    handler = settings_dialog.run_pipeline(tmp_path / 'file_path.config')
    assert handler.manage_calls == [{'confirm_cb': None}]


# --- log file naming/location -------------------------------------------------

def test_build_gui_log_path_uses_final_dir_logs_subdir(tmp_path):
    """Reuses FileHandling.write_log's own 'logs' subdirectory of the final
    storage directory, with a gui_run_<timestamp>.log name distinct from
    write_log's own hobo_qaqc_<timestamp>.log."""
    final_dir = tmp_path / 'final'
    path = settings_dialog.build_gui_log_path(final_dir, timestamp='20260101_120000')
    assert path == final_dir / 'logs' / 'gui_run_20260101_120000.log'


def test_build_gui_log_path_falls_back_to_repo_root_when_no_final_dir():
    path = settings_dialog.build_gui_log_path(None, timestamp='20260101_120000')
    assert path == settings_dialog.REPO_ROOT / 'logs' / 'gui_run_20260101_120000.log'


def test_persist_gui_log_writes_full_text(tmp_path):
    final_dir = tmp_path / 'final'
    log_path = settings_dialog.persist_gui_log(
        'line one\nline two\n', final_dir, timestamp='20260101_120000')

    assert log_path == final_dir / 'logs' / 'gui_run_20260101_120000.log'
    assert log_path.read_text(encoding='utf-8') == 'line one\nline two\n'
