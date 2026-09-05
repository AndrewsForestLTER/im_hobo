"""Tests for hobo_date_summary.deduplicate_and_write's handling of the TOA5/Parquet
sibling files hobo_qaqc.py writes alongside each CSV in bulk mode
(dir_final_storage/TOA5/<stem>.dat, dir_final_storage/parquet/<stem>.parquet).

Bug fixed here: dedupe only knew about .csv files, so a CSV that survived dedupe
(copied unchanged or truncated) left its TOA5/Parquet siblings behind -- confirmed
against real output where bulk_clean/TOA5 and bulk_clean/parquet were populated but
bulk_clean_dedup had neither subdirectory at all. See CHANGELOG.
"""
from MET_hobo.hobo_date_summary import (
    build_dedupe_output_path,
    deduplicate_and_write,
    summarize_directories,
)


def _write_csv(path, timestamps):
    lines = ['Date,Temp,Intensity']
    lines.extend(f'{ts},12.5,100' for ts in timestamps)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _make_final_dir_with_overlap(tmp_path):
    """Synthetic dir_final_storage with two same-sitecode CSVs whose data ranges
    overlap -- one survives dedupe truncated, the other copied unchanged -- each
    with a paired TOA5/<stem>.dat and parquet/<stem>.parquet sibling, matching the
    layout file_manager.qaqc_csv actually produces in bulk mode.
    """
    final_dir = tmp_path / 'bulk_clean'
    (final_dir / 'TOA5').mkdir(parents=True)
    (final_dir / 'parquet').mkdir(parents=True)

    # Earlier file (start 00:00) -- its 00:15/00:30 records fall inside the later
    # file's range and get truncated.
    _write_csv(final_dir / 'PA002_20240601.csv', [
        '2024-06-01 00:00:00', '2024-06-01 00:15:00', '2024-06-01 00:30:00',
    ])
    # Later file (start 00:15) -- nothing later than it, so it's copied unchanged.
    _write_csv(final_dir / 'PA002_20240610.csv', [
        '2024-06-01 00:15:00', '2024-06-01 00:30:00', '2024-06-01 00:45:00',
    ])

    for stem in ('PA002_20240601', 'PA002_20240610'):
        (final_dir / 'TOA5' / f'{stem}.dat').write_text(f'toa5 content for {stem}\n')
        (final_dir / 'parquet' / f'{stem}.parquet').write_bytes(f'parquet bytes for {stem}'.encode())

    return final_dir


def test_dedupe_carries_toa5_and_parquet_siblings_for_both_branches(tmp_path):
    final_dir = _make_final_dir_with_overlap(tmp_path)
    rows = summarize_directories([final_dir])
    assert {r['status'] for r in rows} == {'OK'}

    log_entries = deduplicate_and_write(rows)
    out_dir = build_dedupe_output_path(final_dir)

    actions = {e['filename']: e['action'] for e in log_entries}
    # Sanity check on the scenario itself -- both dedupe code paths are exercised.
    assert actions['PA002_20240601.csv'] == 'truncated — overlapping records removed'
    assert actions['PA002_20240610.csv'] == 'copied unchanged'

    for stem in ('PA002_20240601', 'PA002_20240610'):
        toa5_out = out_dir / 'TOA5' / f'{stem}.dat'
        parquet_out = out_dir / 'parquet' / f'{stem}.parquet'
        assert toa5_out.is_file(), f'missing TOA5 sibling for {stem}'
        assert parquet_out.is_file(), f'missing parquet sibling for {stem}'
        assert toa5_out.read_text() == f'toa5 content for {stem}\n'
        assert parquet_out.read_bytes() == f'parquet bytes for {stem}'.encode()


def test_dedupe_skips_missing_siblings_silently(tmp_path):
    """final_subdirs=True mode (or any CSV without TOA5/parquet siblings, e.g. an
    older run predating this output) must not error -- the dedupe output simply
    gets no TOA5/parquet subdirectory for that file."""
    final_dir = tmp_path / 'bulk_clean'
    final_dir.mkdir()
    _write_csv(final_dir / 'PA010_20240601.csv', ['2024-06-01 00:00:00'])

    rows = summarize_directories([final_dir])
    log_entries = deduplicate_and_write(rows)
    out_dir = build_dedupe_output_path(final_dir)

    assert log_entries[0]['action'] == 'copied unchanged'
    assert (out_dir / 'PA010_20240601.csv').is_file()
    assert not (out_dir / 'TOA5').exists()
    assert not (out_dir / 'parquet').exists()


def test_dedupe_carries_only_existing_sibling_kind(tmp_path):
    """A CSV with only a TOA5 sibling (no parquet, or vice versa) copies just the
    one that exists, without erroring on the missing one."""
    final_dir = tmp_path / 'bulk_clean'
    (final_dir / 'TOA5').mkdir(parents=True)
    _write_csv(final_dir / 'PA020_20240601.csv', ['2024-06-01 00:00:00'])
    (final_dir / 'TOA5' / 'PA020_20240601.dat').write_text('toa5 only\n')

    rows = summarize_directories([final_dir])
    deduplicate_and_write(rows)
    out_dir = build_dedupe_output_path(final_dir)

    assert (out_dir / 'TOA5' / 'PA020_20240601.dat').is_file()
    assert not (out_dir / 'parquet').exists()
