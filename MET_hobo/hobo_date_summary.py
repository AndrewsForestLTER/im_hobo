#!/usr/bin/env python3
"""
HOBO CSV Date Summary, Overlap Viewer, and Deduplicator

Scans one or more directories of cleaned HOBO CSV files, summarizes date
ranges by file, displays a swim lane chart showing temporal coverage and
overlaps grouped by sitecode, and writes deduplicated files to a dedupe
output directory (see build_dedupe_output_path) alongside each source
directory by default, or the configured dir_dedupe_output.

Deduplication rule:
    Where two files share a sitecode and have overlapping timestamps, the
    earlier file loses the overlapping records. The later file is always
    authoritative. All files (modified or not) are written to the dedupe
    output directory so it's always a complete, ready-to-process set.

Requirements:
    pip install matplotlib

Usage:
    python hobo_date_summary.py
"""

if __package__ in (None, ''):
    # Run directly, e.g. `cd MET_hobo; python hobo_date_summary.py` -- MET_hobo/ is
    # not on sys.path as a package in this case, so put its parent there instead.
    # (No absolute `from MET_hobo import ...` is needed here today, but this keeps
    # the bootstrap consistent with file_manager.py for whichever runs first.)
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import csv
import re
import shutil
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.dates as mdates
    import matplotlib.patches as mpatches
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# ── Date parsing ──────────────────────────────────────────────────────────────

DATE_FORMATS = (
    '%Y-%m-%d %H:%M:%S',   # 2021-06-23 04:20:00
    '%Y-%m-%d %H:%M',      # 2021-06-23 04:20  (no seconds - older hobo_qaqc output)
    '%m/%d/%y %I:%M:%S %p',
    '%m/%d/%Y %I:%M:%S %p',
    '%m/%d/%y %I:%M %p',   # 12-hr no seconds
    '%m/%d/%Y %I:%M %p',
    '%m/%d/%y %H:%M:%S',
    '%m/%d/%Y %H:%M:%S',
    '%m/%d/%y %H:%M',      # 24-hr no seconds
    '%m/%d/%Y %H:%M',
)


def parse_date_value(value):
    """Parse a timestamp string from either processed or raw HOBO CSV files."""
    text = value.strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def find_date_column(row):
    """Return the index of the date column in a CSV header row."""
    normalized = [cell.strip().strip('"').lower() for cell in row]
    for idx, cell in enumerate(normalized):
        if cell == 'date':
            return idx
    for idx, cell in enumerate(normalized):
        if cell == 'date time':
            return idx
    for idx, cell in enumerate(normalized):
        if 'date' in cell and 'time' in cell:
            return idx
    for idx, cell in enumerate(normalized):
        if 'date' in cell:
            return idx
    return None


# ── Sitecode extraction ───────────────────────────────────────────────────────

def extract_sitecode(filename):
    """Extract sitecode from HOBO filename.

    Handles both dataset conventions:
        MS045: PA002_20250614.csv          -> 'PA002'
        MV008: PA348_6.5_20260708.csv      -> 'PA348_6.5'

    The trailing '_YYYYMMDD' (optionally followed by HHMM) is the download
    date; everything before it is the sitecode. This preserves the height
    suffix that MV008 filenames carry, without which multiple heights at
    the same site collapse to one sitecode and dedup drops legitimate data
    across all but the latest download.

    Falls back to the first underscore-delimited token when the trailing
    date suffix isn't present, preserving legacy behavior for filenames
    without a date component.
    """
    stem = Path(filename).stem
    parts = stem.split('_')
    if parts and re.fullmatch(r'\d{8}(\d{4})?', parts[-1]):
        return '_'.join(parts[:-1])
    return parts[0]


# ── Raw file parsing ──────────────────────────────────────────────────────────

def read_csv_structure(path):
    """Read a HOBO CSV and return its structural components.

    Returns a dict with:
        preamble_lines  - list of raw text lines before the CSV header
        header_line     - the raw CSV header line (str)
        date_idx        - column index of the date field
        data_rows       - list of (raw_line, canonical_ts) tuples;
                          canonical_ts is None if the row could not be parsed
    """
    raw_lines = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()

    preamble_lines = []
    header_line = None
    date_idx = None
    data_rows = []

    for raw in raw_lines:
        if header_line is None:
            try:
                parsed = next(csv.reader([raw]))
            except StopIteration:
                preamble_lines.append(raw)
                continue

            idx = find_date_column(parsed)
            if idx is not None:
                header_line = raw
                date_idx = idx
            else:
                preamble_lines.append(raw)
        else:
            # Data row — extract and normalise timestamp for dedup keying
            try:
                parsed = next(csv.reader([raw]))
            except StopIteration:
                data_rows.append((raw, None))
                continue

            if date_idx < len(parsed):
                dt = parse_date_value(parsed[date_idx])
                canonical = dt.strftime("%Y-%m-%d %H:%M") if dt else None  # minute precision for cross-deployment dedup
            else:
                canonical = None

            data_rows.append((raw, canonical))

    return {
        'preamble_lines': preamble_lines,
        'header_line': header_line,
        'date_idx': date_idx,
        'data_rows': data_rows,
    }


# ── CSV summarization ─────────────────────────────────────────────────────────

def summarize_csv_file(path):
    """Read a CSV file and return its first and last timestamp."""
    struct = read_csv_structure(path)

    if struct['header_line'] is None:
        return {
            'filename': path.name,
            'sitecode': extract_sitecode(path.name),
            'source_dir': str(path.parent),
            'start_date': '',
            'end_date': '',
            'records': 0,
            'status': 'No Date column found',
            '_path': path,
            '_struct': struct,
        }

    timestamps = [ts for _, ts in struct['data_rows'] if ts is not None]

    if not timestamps:
        return {
            'filename': path.name,
            'sitecode': extract_sitecode(path.name),
            'source_dir': str(path.parent),
            'start_date': '',
            'end_date': '',
            'records': 0,
            'status': 'No valid dates found',
            '_path': path,
            '_struct': struct,
        }

    dts = [datetime.strptime(ts, '%Y-%m-%d %H:%M') for ts in timestamps]

    return {
        'filename': path.name,
        'sitecode': extract_sitecode(path.name),
        'source_dir': str(path.parent),
        'start_date': min(dts).strftime('%Y-%m-%d %H:%M:%S'),
        'end_date': max(dts).strftime('%Y-%m-%d %H:%M:%S'),
        'records': len(timestamps),
        'status': 'OK',
        '_path': path,
        '_struct': struct,
    }


def summarize_directories(directories, progress_cb=None):
    """Return date summaries for all CSV files across a list of directories.

    Args:
        directories:  list of directory paths to scan
        progress_cb:  optional callable(completed, total) called after each file
    """
    # Count total files first so the progress bar is accurate
    all_paths = []
    for directory in directories:
        all_paths.extend(sorted(Path(directory).glob('*.csv')))
    total = len(all_paths)

    rows = []
    for i, path in enumerate(all_paths):
        try:
            rows.append(summarize_csv_file(path))
        except Exception as exc:
            rows.append({
                'filename': path.name,
                'sitecode': extract_sitecode(path.name),
                'source_dir': str(path.parent),
                'start_date': '',
                'end_date': '',
                'records': 0,
                'status': f'Error: {exc}',
                '_path': path,
                '_struct': None,
            })
        if progress_cb:
            progress_cb(i + 1, total)
    return rows


# ── Overlap detection ─────────────────────────────────────────────────────────

def compute_overlaps(rows):
    """Identify files that overlap with another file sharing the same sitecode.

    Returns:
        overlapping_files   - set of filenames involved in at least one overlap
        overlap_intervals   - list of (sitecode, start_dt, end_dt) tuples
    """
    by_site = defaultdict(list)
    for row in rows:
        if row['status'] != 'OK':
            continue
        start = datetime.strptime(row['start_date'], '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(row['end_date'], '%Y-%m-%d %H:%M:%S')
        by_site[row['sitecode']].append((row['filename'], start, end))

    overlapping_files = set()
    overlap_intervals = []

    for sc, files in by_site.items():
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                fn_a, start_a, end_a = files[i]
                fn_b, start_b, end_b = files[j]
                ov_start = max(start_a, start_b)
                ov_end = min(end_a, end_b)
                if ov_start < ov_end:
                    overlapping_files.add(fn_a)
                    overlapping_files.add(fn_b)
                    overlap_intervals.append((sc, ov_start, ov_end))

    return overlapping_files, overlap_intervals


# ── Deduplication engine ──────────────────────────────────────────────────────

def build_dedupe_output_path(source_dir, configured=None):
    """Return the dedupe output directory for a given source directory.

    If `configured` is given (e.g. file_path.config's dir_dedupe_output), that
    path is used as-is, regardless of source_dir. Otherwise defaults to a
    sibling of source_dir named '<source_dir name>_dedup' -- e.g. a source_dir
    of .../bulk_clean defaults to .../bulk_clean_dedup.
    """
    if configured is not None:
        return Path(configured)
    source_dir = Path(source_dir)
    return source_dir.parent / (source_dir.name + '_dedup')


def deduplicate_and_write(rows, progress_cb=None, dedupe_output=None):
    """Write all files to the dedupe output directory; remove overlapping
    timestamps from earlier files where a later file for the same sitecode is
    authoritative.

    dedupe_output, if given, is passed as `configured` to
    build_dedupe_output_path for every row, so all rows are written to that
    single directory regardless of their individual source_dir. Otherwise each
    row gets its own default sibling directory (see build_dedupe_output_path).

    Strategy:
        1. Group OK files by sitecode; sort each group by start_date ascending.
        2. For each file, collect every timestamp that appears in any later file
           with the same sitecode — those timestamps are removed from this file.
        3. All files (modified or not) are written to the dedupe output directory.
        4. Error files are copied as-is with a note in the log.
        5. A timestamped dedup_log CSV is written to a logs/ subfolder of each
           dedupe output folder (kept out of the *.csv glob used to scan for data).

    Returns:
        log_entries - list of dicts describing what happened to each file
    """
    # ── Step 1: group and sort OK rows by sitecode ────────────────────────────
    by_site = defaultdict(list)
    for row in rows:
        if row['status'] != 'OK':
            continue
        start_dt = datetime.strptime(row['start_date'], '%Y-%m-%d %H:%M:%S')
        by_site[row['sitecode']].append((start_dt, row))

    for sc in by_site:
        by_site[sc].sort(key=lambda x: x[0])  # ascending by start date

    # ── Step 2: build "timestamps to remove" set for each file ───────────────
    # Strategy: remove any record from an earlier file whose timestamp falls
    # *within the date range* of a later file for the same sitecode.
    #
    # This handles the common case where two sensors at the same site log at
    # the same interval but with different sub-interval offsets (e.g., one
    # records at HH:11/31/51, another at HH:00/20/40). Exact timestamp
    # matching fails in that case; range-based removal is the correct approach
    # because the later download supersedes the earlier one for that period.
    #
    # Key: (source_dir, filename) -> set of canonical timestamp strings to drop
    remove_map = defaultdict(set)

    for sc, file_list in by_site.items():
        n = len(file_list)
        for i in range(n):
            _, row_i = file_list[i]

            # Collect the date ranges covered by all later files at this site
            later_ranges = []
            for j in range(i + 1, n):
                _, row_j = file_list[j]
                try:
                    s = datetime.strptime(row_j['start_date'], '%Y-%m-%d %H:%M:%S')
                    e = datetime.strptime(row_j['end_date'],   '%Y-%m-%d %H:%M:%S')
                    later_ranges.append((s, e))
                except ValueError:
                    continue

            if not later_ranges:
                continue

            # Mark any timestamp in row_i that falls inside a later file's range
            to_remove = set()
            for _, ts in row_i['_struct']['data_rows']:
                if ts is None:
                    continue
                try:
                    dt = datetime.strptime(ts, '%Y-%m-%d %H:%M')
                except ValueError:
                    continue
                for s, e in later_ranges:
                    if s <= dt <= e:
                        to_remove.add(ts)
                        break

            if to_remove:
                remove_map[(row_i['source_dir'], row_i['filename'])] = to_remove

    # ── Step 3: write all files ───────────────────────────────────────────────
    log_entries = []
    written_dirs = set()

    total_files = len(rows)
    files_done = 0

    for row in rows:
        if row['status'] != 'OK':
            files_done += 1
            if progress_cb:
                progress_cb(files_done, total_files)
            continue

        src_path = row['_path']
        out_dir = build_dedupe_output_path(row['source_dir'], configured=dedupe_output)
        out_dir.mkdir(parents=True, exist_ok=True)
        written_dirs.add(out_dir)
        out_path = out_dir / row['filename']

        struct = row['_struct']
        key = (row['source_dir'], row['filename'])
        to_remove = remove_map.get(key, set())

        if not to_remove:
            # No overlap — copy file as-is
            shutil.copy2(src_path, out_path)
            log_entries.append({
                'filename': row['filename'],
                'source_dir': row['source_dir'],
                'sitecode': row['sitecode'],
                'records_in': row['records'],
                'records_removed': 0,
                'records_out': row['records'],
                'action': 'copied unchanged',
                'status': 'OK',
            })
            files_done += 1
            if progress_cb:
                progress_cb(files_done, total_files)
        else:
            # Build filtered file line by line
            removed_count = 0
            lines_out = []

            # Preamble: annotate the first non-empty preamble line
            annotated = False
            for pline in struct['preamble_lines']:
                if not annotated and pline.strip():
                    lines_out.append(
                        pline.rstrip() + ' [this file has been truncated]')
                    annotated = True
                else:
                    lines_out.append(pline)

            # CSV header
            if struct['header_line'] is not None:
                lines_out.append(struct['header_line'])

            # Data rows: drop timestamps present in a later file
            for raw_line, ts in struct['data_rows']:
                if ts is not None and ts in to_remove:
                    removed_count += 1
                else:
                    lines_out.append(raw_line)

            out_path.write_text('\n'.join(lines_out) + '\n', encoding='utf-8')

            records_out = row['records'] - removed_count
            log_entries.append({
                'filename': row['filename'],
                'source_dir': row['source_dir'],
                'sitecode': row['sitecode'],
                'records_in': row['records'],
                'records_removed': removed_count,
                'records_out': records_out,
                'action': 'truncated — overlapping records removed',
                'status': 'OK',
            })

        files_done += 1
        if progress_cb:
            progress_cb(files_done, total_files)

    # Error rows: copy as-is where possible
    for row in rows:
        if row['status'] == 'OK':
            continue
        src_path = row.get('_path')
        out_dir = build_dedupe_output_path(row['source_dir'], configured=dedupe_output)
        out_dir.mkdir(parents=True, exist_ok=True)
        written_dirs.add(out_dir)

        if src_path and src_path.exists():
            shutil.copy2(src_path, out_dir / row['filename'])
            action = 'copied with errors — review manually'
        else:
            action = 'skipped — source file not accessible'

        log_entries.append({
            'filename': row['filename'],
            'source_dir': row['source_dir'],
            'sitecode': row['sitecode'],
            'records_in': 0,
            'records_removed': 0,
            'records_out': 0,
            'action': action,
            'status': row['status'],
        })

    # ── Step 4: write one timestamped log per output directory ────────────────
    # Written to a logs/ subfolder, not out_dir itself, so it isn't picked up
    # as a data file by summarize_directories()'s *.csv glob on out_dir.
    run_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    for out_dir in written_dirs:
        dir_entries = [
            e for e in log_entries
            if build_dedupe_output_path(e['source_dir'], configured=dedupe_output) == out_dir
        ]
        log_dir = out_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f'dedup_log_{run_ts}.csv'
        with log_path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                'filename', 'sitecode', 'source_dir',
                'records_in', 'records_removed', 'records_out',
                'action', 'status',
            ])
            writer.writeheader()
            writer.writerows(dir_entries)

    return log_entries


# ── Swim lane chart ───────────────────────────────────────────────────────────

COLOR_NORMAL       = '#4C8BB5'   # steel blue – file has no overlap
COLOR_OVERLAP_FILE = '#E07B39'   # orange     – file overlaps with another
COLOR_OV_REGION    = '#D93025'   # red        – the actual overlap region
LANE_HEIGHT        = 0.72        # total height of each sitecode lane


def build_swim_lane_figure(rows):
    """Build and return a matplotlib Figure containing the swim lane chart."""
    ok_rows = [r for r in rows if r['status'] == 'OK']

    if not ok_rows:
        fig = Figure(figsize=(10, 4))
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'No valid data to display.',
                transform=ax.transAxes, ha='center', va='center', fontsize=12)
        return fig

    overlapping_files, overlap_intervals = compute_overlaps(rows)

    by_site = defaultdict(list)
    for row in ok_rows:
        start = datetime.strptime(row['start_date'], '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(row['end_date'], '%Y-%m-%d %H:%M:%S')
        by_site[row['sitecode']].append((row['filename'], start, end))

    for sc in by_site:
        by_site[sc].sort(key=lambda x: x[1])

    sitecodes = sorted(by_site.keys())
    n_sites = len(sitecodes)

    fig_height = max(5, n_sites * 0.38 + 2.5)
    fig = Figure(figsize=(14, fig_height), tight_layout=True)
    ax = fig.add_subplot(111)

    for y_pos, sc in enumerate(sitecodes):
        files = by_site[sc]
        n_files = len(files)
        sub_height = LANE_HEIGHT / n_files

        for sub_idx, (fn, start, end) in enumerate(files):
            y_center = y_pos - LANE_HEIGHT / 2 + (sub_idx + 0.5) * sub_height
            bar_height = sub_height * 0.82
            color = COLOR_OVERLAP_FILE if fn in overlapping_files else COLOR_NORMAL
            x_left = mdates.date2num(start)
            x_width = mdates.date2num(end) - x_left
            ax.barh(y_center, x_width, left=x_left, height=bar_height,
                    color=color, alpha=0.88, align='center')

        for ov_sc, ov_start, ov_end in overlap_intervals:
            if ov_sc == sc:
                x_left = mdates.date2num(ov_start)
                x_width = mdates.date2num(ov_end) - x_left
                ax.barh(y_pos, x_width, left=x_left, height=LANE_HEIGHT,
                        color=COLOR_OV_REGION, alpha=0.40, align='center')

    ax.set_yticks(range(n_sites))
    ax.set_yticklabels(sitecodes, fontsize=7)
    ax.set_ylim(-0.6, n_sites - 0.4)
    ax.invert_yaxis()

    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    for label in ax.xaxis.get_majorticklabels():
        label.set_rotation(45)
        label.set_ha('right')
        label.set_fontsize(8)

    ax.set_xlabel('Date', fontsize=9)
    ax.set_title('HOBO CSV Temporal Coverage by Site Code', fontsize=11, pad=10)
    ax.grid(axis='x', linestyle='--', linewidth=0.5, alpha=0.5)

    legend_handles = [
        mpatches.Patch(color=COLOR_NORMAL, label='No overlap'),
        mpatches.Patch(color=COLOR_OVERLAP_FILE, label='File overlaps with another'),
        mpatches.Patch(color=COLOR_OV_REGION, alpha=0.6, label='Overlap region'),
    ]
    ax.legend(handles=legend_handles, loc='lower right', fontsize=8, framealpha=0.9)

    return fig


# ── Application ───────────────────────────────────────────────────────────────

class CsvDateSummaryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('HOBO CSV Date Summary')
        self.geometry('1100x720')
        self.minsize(900, 520)

        self.selected_dirs = []
        self.status_var = tk.StringVar(
            value='Add one or more source folders, then click Scan.')
        self.rows = []
        self._chart_canvas = None

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        folder_frame = ttk.LabelFrame(self, text='Source Folders', padding=8)
        folder_frame.pack(fill='x', padx=12, pady=(10, 0))

        list_frame = ttk.Frame(folder_frame)
        list_frame.pack(fill='x')

        self.dir_listbox = tk.Listbox(
            list_frame, height=4, selectmode='extended', font=('Courier', 9))
        dir_scroll = ttk.Scrollbar(
            list_frame, orient='horizontal', command=self.dir_listbox.xview)
        self.dir_listbox.configure(xscrollcommand=dir_scroll.set)
        self.dir_listbox.pack(fill='x', expand=True)
        dir_scroll.pack(fill='x')

        btn_frame = ttk.Frame(folder_frame)
        btn_frame.pack(fill='x', pady=(6, 0))
        ttk.Button(btn_frame, text='Add Folder…',
                   command=self.add_folder).pack(side='left')
        ttk.Button(btn_frame, text='Remove Selected',
                   command=self.remove_selected_folders).pack(side='left', padx=(6, 0))
        ttk.Button(btn_frame, text='Clear All',
                   command=self.clear_folders).pack(side='left', padx=(6, 0))

        action_frame = ttk.Frame(self, padding=(12, 6))
        action_frame.pack(fill='x')
        self._action_buttons = []

        btn_scan = ttk.Button(action_frame, text='Scan',
                              command=self.scan_directories)
        btn_scan.pack(side='left')
        self._action_buttons.append(btn_scan)

        btn_save = ttk.Button(action_frame, text='Save Summary CSV',
                              command=self.save_summary)
        btn_save.pack(side='left', padx=(8, 0))
        self._action_buttons.append(btn_save)

        if MATPLOTLIB_AVAILABLE:
            btn_chart = ttk.Button(action_frame, text='Save Chart PNG',
                                   command=self.save_chart)
            btn_chart.pack(side='left', padx=(8, 0))
            self._action_buttons.append(btn_chart)

        btn_dedup = ttk.Button(action_frame, text='Deduplicate',
                               command=self.run_deduplication)
        btn_dedup.pack(side='left', padx=(8, 0))
        self._action_buttons.append(btn_dedup)

        # Progress bar — shown only during background operations
        progress_frame = ttk.Frame(self, padding=(12, 0))
        progress_frame.pack(fill='x')
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self._progress_var,
            maximum=100,
            mode='determinate',
        )
        self._progress_bar.pack(fill='x')
        self._progress_label = ttk.Label(progress_frame, text='', font=('TkDefaultFont', 8))
        self._progress_label.pack(anchor='e', pady=(1, 4))
        self._progress_bar.pack_forget()    # hidden until needed
        self._progress_label.pack_forget()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=12, pady=(0, 0))

        summary_tab = ttk.Frame(self.notebook)
        self.notebook.add(summary_tab, text='File Summary')
        self._build_summary_table(summary_tab)

        self.chart_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.chart_tab, text='Overlap Chart')
        if MATPLOTLIB_AVAILABLE:
            ttk.Label(self.chart_tab,
                      text='Run a scan to generate the overlap chart.',
                      padding=20).pack()
        else:
            ttk.Label(self.chart_tab,
                      text='matplotlib is not installed.\n'
                           'Run:  pip install matplotlib',
                      padding=20, foreground='red').pack()

        ttk.Label(self, textvariable=self.status_var,
                  padding=(12, 4)).pack(fill='x')

    def _build_summary_table(self, parent):
        cols = ('filename', 'sitecode', 'start_date', 'end_date', 'records', 'status')
        self.tree = ttk.Treeview(parent, columns=cols, show='headings')

        self.tree.heading('filename',   text='Filename')
        self.tree.heading('sitecode',   text='Site Code')
        self.tree.heading('start_date', text='Start Date')
        self.tree.heading('end_date',   text='End Date')
        self.tree.heading('records',    text='Records')
        self.tree.heading('status',     text='Status')

        self.tree.column('filename',   width=240, anchor='w')
        self.tree.column('sitecode',   width=80,  anchor='w')
        self.tree.column('start_date', width=160, anchor='w')
        self.tree.column('end_date',   width=160, anchor='w')
        self.tree.column('records',    width=80,  anchor='e')
        self.tree.column('status',     width=200, anchor='w')

        yscroll = ttk.Scrollbar(parent, orient='vertical',   command=self.tree.yview)
        xscroll = ttk.Scrollbar(parent, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')

        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

    def _set_buttons_state(self, state):
        """Enable or disable all action buttons during background operations."""
        for widget in self._action_buttons:
            widget.configure(state=state)

    def _show_progress(self, show):
        """Show or hide the progress bar and label."""
        if show:
            self._progress_bar.pack(fill='x')
            self._progress_label.pack(anchor='e', pady=(1, 4))
        else:
            self._progress_bar.pack_forget()
            self._progress_label.pack_forget()
            self._progress_var.set(0)
            self._progress_label.configure(text='')

    def _update_progress(self, completed, total):
        """Called from background thread via self.after() to update progress bar."""
        pct = (completed / total * 100) if total else 0
        self._progress_var.set(pct)
        self._progress_label.configure(
            text=f'{completed} / {total} files  ({pct:.0f}%)')

    # ── Folder management ─────────────────────────────────────────────────────

    def add_folder(self):
        initial = self.selected_dirs[-1] if self.selected_dirs else str(Path.cwd())
        selected = filedialog.askdirectory(
            title='Select a folder of CSV files', initialdir=initial)
        if selected and selected not in self.selected_dirs:
            self.selected_dirs.append(selected)
            self.dir_listbox.insert('end', selected)

    def remove_selected_folders(self):
        for idx in reversed(self.dir_listbox.curselection()):
            self.dir_listbox.delete(idx)
            del self.selected_dirs[idx]

    def clear_folders(self):
        self.dir_listbox.delete(0, 'end')
        self.selected_dirs.clear()

    # ── Scan ──────────────────────────────────────────────────────────────────

    def scan_directories(self):
        if not self.selected_dirs:
            messagebox.showwarning(
                'No folders selected',
                'Add at least one source folder before scanning.')
            return

        missing = [d for d in self.selected_dirs if not Path(d).is_dir()]
        if missing:
            messagebox.showerror(
                'Invalid folder',
                'One or more folders no longer exist:\n' + '\n'.join(missing))
            return

        self._set_buttons_state('disabled')
        self._show_progress(True)
        self.status_var.set('Scanning files...')
        self.update_idletasks()

        def _progress(completed, total):
            self.after(0, lambda c=completed, t=total: self._update_progress(c, t))

        def _run():
            rows = summarize_directories(self.selected_dirs, progress_cb=_progress)
            self.after(0, lambda: self._scan_complete(rows))

        threading.Thread(target=_run, daemon=True).start()

    def _scan_complete(self, rows):
        self.rows = rows
        self._show_progress(False)
        self._refresh_table()

        if MATPLOTLIB_AVAILABLE:
            self._refresh_chart()

        ok_count = sum(1 for r in self.rows if r['status'] == 'OK')
        _, overlap_intervals = compute_overlaps(self.rows)
        overlap_sites = len(set(sc for sc, _, _ in overlap_intervals))

        msg = (f'Scanned {len(self.rows)} file(s) across '
               f'{len(self.selected_dirs)} folder(s). {ok_count} summarized OK.')
        if overlap_sites:
            msg += (f'  \u26a0 Overlaps found at {overlap_sites} site(s) — '
                    f'see Overlap Chart or run Deduplicate.')
        self.status_var.set(msg)
        self._set_buttons_state('normal')

    # ── Table refresh ─────────────────────────────────────────────────────────

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.rows:
            self.tree.insert('', 'end', values=(
                row['filename'],
                row['sitecode'],
                row['start_date'],
                row['end_date'],
                row['records'],
                row['status'],
            ))

    # ── Chart refresh ─────────────────────────────────────────────────────────

    def _refresh_chart(self):
        for widget in self.chart_tab.winfo_children():
            widget.destroy()

        self._current_fig = build_swim_lane_figure(self.rows)

        canvas = FigureCanvasTkAgg(self._current_fig, master=self.chart_tab)
        canvas.draw()

        toolbar = NavigationToolbar2Tk(canvas, self.chart_tab)
        toolbar.update()

        toolbar.pack(side='bottom', fill='x')
        canvas.get_tk_widget().pack(fill='both', expand=True)

        self._chart_canvas = canvas

    # ── Deduplication ─────────────────────────────────────────────────────────

    def run_deduplication(self):
        if not self.rows:
            messagebox.showwarning('No data',
                                   'Run a scan before deduplicating.')
            return

        _, overlap_intervals = compute_overlaps(self.rows)
        if not overlap_intervals:
            messagebox.showinfo(
                'No overlaps found',
                'No overlapping timestamps detected. '
                'All files will be copied unchanged to the dedupe output directory.')

        out_dirs = sorted(set(
            str(build_dedupe_output_path(r['source_dir'])) for r in self.rows
        ))
        dir_preview = '\n'.join(out_dirs)

        proceed = messagebox.askyesno(
            'Confirm Deduplication',
            f'All files will be written to:\n\n{dir_preview}\n\n'
            f'Overlapping records will be removed from earlier files.\n'
            f'A dedup_log CSV will be saved in a logs/ subfolder of each output folder.\n\n'
            f'Proceed?'
        )
        if not proceed:
            return

        self._set_buttons_state('disabled')
        self._show_progress(True)
        self.status_var.set('Deduplicating files...')
        self.update_idletasks()

        source_rows = self.rows  # capture before thread starts

        def _progress(completed, total):
            self.after(0, lambda c=completed, t=total: self._update_progress(c, t))

        def _run():
            try:
                log_entries = deduplicate_and_write(source_rows, progress_cb=_progress)
            except Exception as exc:
                err_msg = str(exc)
                self.after(0, lambda: (
                    messagebox.showerror('Deduplication error', err_msg),
                    self._show_progress(False),
                    self._set_buttons_state('normal')
                ))
                return
            self.after(0, lambda: self._dedup_complete(log_entries, source_rows))

        threading.Thread(target=_run, daemon=True).start()

    def _dedup_complete(self, log_entries, source_rows):
        total = len(log_entries)
        truncated = sum(1 for e in log_entries if e['records_removed'] > 0)
        total_removed = sum(e['records_removed'] for e in log_entries)

        # ── Auto-rescan the dedupe output directory(ies) ──────────────────────
        self._show_progress(False)  # reset before rescan shows its own progress
        self.status_var.set(
            f'Done. {total} file(s) written. Re-scanning dedupe output...')
        self.update_idletasks()

        dedupe_dirs = sorted(set(
            str(build_dedupe_output_path(r['source_dir'])) for r in source_rows
        ))
        dedupe_dirs = [d for d in dedupe_dirs if Path(d).is_dir()]

        if dedupe_dirs:
            self.selected_dirs = dedupe_dirs
            self.dir_listbox.delete(0, 'end')
            for d in dedupe_dirs:
                self.dir_listbox.insert('end', d)

            self._show_progress(True)
            self.status_var.set('Re-scanning dedupe output...')

            def _progress(completed, total):
                self.after(0, lambda c=completed, t=total: self._update_progress(c, t))

            def _rescan():
                rows = summarize_directories(self.selected_dirs, progress_cb=_progress)
                self.after(0, lambda: self._rescan_complete(
                    rows, truncated, total_removed))

            threading.Thread(target=_rescan, daemon=True).start()
        else:
            msg = (f'Done. {total} file(s) written to the dedupe output directory. '
                   f'{truncated} file(s) truncated, '
                   f'{total_removed} duplicate record(s) removed.')
            self.status_var.set(msg)
            messagebox.showinfo('Deduplication complete', msg)
            self._set_buttons_state('normal')

    def _rescan_complete(self, rows, truncated, total_removed):
        self.rows = rows
        self._show_progress(False)
        self._refresh_table()

        if MATPLOTLIB_AVAILABLE:
            self._refresh_chart()

        ok_count = sum(1 for r in self.rows if r['status'] == 'OK')
        _, remaining_overlaps = compute_overlaps(self.rows)
        overlap_sites = len(set(sc for sc, _, _ in remaining_overlaps))

        if overlap_sites:
            final_msg = (f'Dedupe output scan complete: {ok_count} file(s). '
                         f'\u26a0 {overlap_sites} site(s) still have overlaps '
                         f'\u2014 review Overlap Chart.')
        else:
            final_msg = (f'Dedupe output scan complete: {ok_count} file(s). '
                         f'\u2713 No overlaps detected.')

        self.status_var.set(final_msg)
        self._set_buttons_state('normal')
        messagebox.showinfo(
            'Deduplication complete',
            f'{truncated} file(s) truncated, '
            f'{total_removed} duplicate record(s) removed.\n\n'
            + final_msg)

    # ── Save actions ──────────────────────────────────────────────────────────

    def save_summary(self):
        if not self.rows:
            messagebox.showinfo('Nothing to save',
                                'Run a scan before saving the summary.')
            return

        initial_name = f'hobo_date_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        save_path = filedialog.asksaveasfilename(
            title='Save summary CSV',
            defaultextension='.csv',
            initialfile=initial_name,
            filetypes=[('CSV files', '*.csv')],
        )
        if not save_path:
            return

        with Path(save_path).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=['filename', 'sitecode', 'source_dir',
                            'start_date', 'end_date', 'records', 'status'],
            )
            writer.writeheader()
            for row in self.rows:
                writer.writerow({k: v for k, v in row.items()
                                 if not k.startswith('_')})

        self.status_var.set(f'Saved summary to {save_path}')

    def save_chart(self):
        if not hasattr(self, '_current_fig'):
            messagebox.showinfo('Nothing to save',
                                'Run a scan before saving the chart.')
            return

        initial_name = f'hobo_overlap_chart_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        save_path = filedialog.asksaveasfilename(
            title='Save chart as PNG',
            defaultextension='.png',
            initialfile=initial_name,
            filetypes=[('PNG image', '*.png'), ('PDF document', '*.pdf')],
        )
        if not save_path:
            return

        self._current_fig.savefig(save_path, dpi=150, bbox_inches='tight')
        self.status_var.set(f'Saved chart to {save_path}')


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = CsvDateSummaryApp()
    app.mainloop()


if __name__ == '__main__':
    main()