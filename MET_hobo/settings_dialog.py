#!/usr/bin/env python3
"""
Settings dialog, pipeline Run button, and Help menu for the HOBO CSV Date Summary
tkinter GUI (hobo_date_summary.py).

Lets a user graphically edit ``file_path.config`` (see doc/source/config_file.rst),
kick off ``FileHandling(...).manage()`` in a background thread, watch its log in a
scrolled text pane, and get a persisted copy of that log after the run. All widget
updates from the background thread go through Tk's ``after()`` so the run thread
never touches a Tk widget directly.

The config read/write and pipeline-invocation logic (CONFIG_FIELDS, build_config_text,
resolve_settings_config_path, run_pipeline, build_gui_log_path) is factored out of the
Tk classes so it can be unit tested without a display -- see dev_tests/test_settings.py.
"""

if __package__ in (None, ''):
    # Run directly -- MET_hobo/ is not on sys.path as a package in this case, so put
    # its parent there instead. Matches the bootstrap in file_manager.py and
    # hobo_date_summary.py.
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import ast
import sys
import threading
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from MET_hobo.file_manager import FileHandling

REPO_ROOT = Path(__file__).resolve().parent.parent

# Canonical docs URL -- see README.rst's "See module documentation ... for use.".
DOCS_URL = 'https://im-hobo.readthedocs.io'


# ── Config schema ─────────────────────────────────────────────────────────────
#
# One entry per file_path.config key FileHandling actually reads (see
# FileHandling.__init__, FileHandling._TOA5_CONFIG_KEYS, and
# doc/source/config_file.rst). Help text is drawn from that doc page and the
# README's "Deduplication (optional)" / "TOA5 and Parquet Output" sections rather
# than reinvented here.
#
# kind:
#   'dir'    - a directory path; gets a Browse (askdirectory) button
#   'str'    - a plain string
#   'choice' - one of a fixed set of strings (ttk.Combobox)
#   'dict'   - a python dict literal, edited as text (e.g. map_fname2dir)

CONFIG_FIELDS = [
    dict(key='dir_source_files', label='Source files directory', kind='dir', required=True,
         help='QAQC is attempted on every CSV file in this directory. Can be a server path.'),
    dict(key='dir_local_processing', label='Local processing directory', kind='dir', required=True,
         help='Temporary working directory, populated during processing and wiped when '
              'processing completes. Recommended to be local to the machine running the pipeline.'),
    dict(key='dir_final_storage', label='Final storage directory', kind='dir', required=True,
         help='Where processed files are ultimately saved. WARNING: cleared on every run -- '
              'do not point this at a directory containing other files.'),
    dict(key='time_step', label='Time step', kind='str', required=False,
         help='Legacy/optional. Only applied when explicitly passed at runtime -- has no '
              "effect on a normal run. A pandas timeseries offset string, e.g. '15min'."),
    dict(key='dedupe_mode', label='Dedupe mode', kind='choice', required=False,
         choices=['off', 'auto', 'prompt'], default='off',
         help='"auto" = dedupe final output after each run. "prompt" = ask before dedupe '
              '(GUI runs show a Yes/No dialog instead of a console prompt). '
              '"off" (or absent) = skip dedupe.'),
    dict(key='dir_dedupe_output', label='Dedupe output directory', kind='dir', required=False,
         help='Optional. Where dedupe_mode writes deduplicated output. Left blank, defaults to '
              'a sibling of the final storage directory named "<name>_dedup".'),
    dict(key='map_fname2dir', label='Filename → project map', kind='dict', required=False,
         help='Optional Python dict routing output into per-project subdirectories by filename '
              "prefix, e.g. {'RS': 'REFSTAND'}. Leave blank to disable."),
    dict(key='toa5_station', label='TOA5 station', kind='str', required=False,
         help='Optional TOA5 header field: station name. Blank if unset.'),
    dict(key='toa5_logger_model', label='TOA5 logger model', kind='str', required=False,
         help='Optional TOA5 header field: logger model. Blank if unset.'),
    dict(key='toa5_serial', label='TOA5 serial', kind='str', required=False,
         help='Optional TOA5 header field: logger serial number. If unset, the serial parsed '
              "from the source file's header (LGR S/N:) is used instead."),
    dict(key='toa5_table_name', label='TOA5 table name', kind='str', required=False,
         help='Optional TOA5 header field: table name. Blank if unset.'),
    dict(key='toa5_os_version', label='TOA5 OS version', kind='str', required=False,
         help='Optional TOA5 header field: datalogger OS version. Blank if unset.'),
    dict(key='toa5_program_name', label='TOA5 program name', kind='str', required=False,
         help='Optional TOA5 header field: program name. Blank if unset.'),
    dict(key='toa5_program_sig', label='TOA5 program signature', kind='str', required=False,
         help='Optional TOA5 header field: program signature. Blank if unset.'),
]

_REQUIRED_KEYS = [f['key'] for f in CONFIG_FIELDS if f.get('required')]


# ── Config path resolution / read / write ─────────────────────────────────────

def resolve_settings_config_path():
    """Return (path, exists) for the config the dialog should load and save to.

    Mirrors FileHandling._resolve_config_path's resolution order (explicit > env
    var > cwd > repo root) but never raises: falls back to <repo root>/file_path.config
    as the save target when nothing is found, so a first-time user always has
    somewhere to save to.
    """
    try:
        path = Path(FileHandling._resolve_config_path(None))
    except FileNotFoundError:
        path = REPO_ROOT / 'file_path.config'
    return path, path.exists()


def load_field_values(path, exists):
    """Return a {key: value} dict (native python types) to seed the dialog with.

    Loads `path` if it exists; otherwise falls back to file_path.config.example
    (seeding the dialog from the template, per the example's own values) or an
    empty dict if even that is missing.
    """
    if exists:
        return FileHandling.load_config(path)
    example = REPO_ROOT / 'file_path.config.example'
    if example.exists():
        return FileHandling.load_config(example)
    return {}


def format_config_value(value):
    """Render a python value as a literal FileHandling.load_config can re-parse
    (it evaluates the right-hand side of each ``key = ...`` line via ast.literal_eval)."""
    return repr(value)


def build_config_text(values):
    """Build full file_path.config text from a {key: value} dict.

    Only keys with a non-empty value are written, preserving the "or key absent"
    semantics documented for optional keys (dedupe_mode, dir_dedupe_output, toa5_*).
    """
    lines = [
        '"""file_path.config -- written by the Settings dialog.',
        '',
        'Edit by hand or reopen via Settings... in the HOBO CSV Date Summary GUI.',
        'See doc/source/config_file.rst for what each key does.',
        '"""',
        '',
    ]
    for field in CONFIG_FIELDS:
        value = values.get(field['key'])
        if value in (None, ''):
            continue
        lines.append(f"{field['key']} = {format_config_value(value)}")
    return '\n'.join(lines) + '\n'


def write_config_file(path, values):
    """Write `values` to `path` as file_path.config, creating parent dirs as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_config_text(values), encoding='utf-8')


# ── Pipeline invocation ────────────────────────────────────────────────────────

def run_pipeline(config_path, confirm_cb=None):
    """Construct FileHandling for config_path and run it.

    Factored out of RunController/SettingsDialog so tests can monkeypatch
    FileHandling here directly -- verifying the call is wired correctly (config
    path passed through, confirm_cb passed through) without constructing a real
    FileHandling, which touches real directories as a side effect of __init__.
    """
    handler = FileHandling(config=str(config_path))
    handler.manage(confirm_cb=confirm_cb)
    return handler


# ── Log persistence ────────────────────────────────────────────────────────────

def build_gui_log_path(final_dir, timestamp=None):
    """Return the path a GUI-triggered run's full log should be written to.

    Reuses FileHandling.write_log's own convention -- a 'logs' subdirectory of the
    final storage directory -- rather than inventing a new location. Named
    distinctly (gui_run_* vs write_log's hobo_qaqc_*) so the two don't collide.
    Falls back to a 'logs' directory at the repo root if final_dir isn't known
    (e.g. Run attempted before a final storage directory was ever configured).
    """
    ts = timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
    base = Path(final_dir) if final_dir else REPO_ROOT
    return base / 'logs' / f'gui_run_{ts}.log'


def persist_gui_log(text, final_dir, timestamp=None):
    """Write `text` to build_gui_log_path(...) and return the path written."""
    path = build_gui_log_path(final_dir, timestamp=timestamp)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


# ── Help ───────────────────────────────────────────────────────────────────────

def open_help():
    """Open project docs: Read the Docs if a browser controller is available,
    else the local built HTML, else the README directly."""
    if webbrowser.open(DOCS_URL):
        return
    local_html = REPO_ROOT / 'doc' / 'build' / 'html' / 'index.html'
    if local_html.exists():
        webbrowser.open(local_html.resolve().as_uri())
        return
    webbrowser.open((REPO_ROOT / 'README.rst').resolve().as_uri())


# ── Tooltip ────────────────────────────────────────────────────────────────────

class Tooltip:
    """Minimal hover tooltip for a "(?)" help label -- a borderless Toplevel shown
    near the widget while the pointer is over it."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind('<Enter>', self._show)
        widget.bind('<Leave>', self._hide)

    def _show(self, _event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f'+{x}+{y}')
        label = tk.Label(self.tip, text=self.text, justify='left', background='#ffffe0',
                          relief='solid', borderwidth=1, wraplength=360, font=('TkDefaultFont', 8))
        label.pack(ipadx=4, ipady=2)

    def _hide(self, _event=None):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


# ── Thread-safe log widget writer ──────────────────────────────────────────────

class _TextRedirector:
    """File-like object that appends text to a scrolledtext widget.

    write() is called from the background pipeline thread; it never touches the
    widget itself, only schedules the append via widget.after(0, ...), which runs
    on the main/Tk thread.
    """

    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        if text:
            self.widget.after(0, self._append, text)

    def flush(self):
        pass

    def _append(self, text):
        self.widget.configure(state='normal')
        self.widget.insert('end', text)
        self.widget.see('end')
        self.widget.configure(state='disabled')


# ── Settings dialog ────────────────────────────────────────────────────────────

class SettingsDialog(tk.Toplevel):
    """Modal dialog to edit file_path.config, then Run the pipeline against it."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title('Pipeline Settings')
        self.geometry('760x760')
        self.minsize(640, 520)
        self.transient(parent)

        self.config_path, exists = resolve_settings_config_path()
        self._initial_values = load_field_values(self.config_path, exists)
        self._saved_values = None
        self._run_thread = None

        self._vars = {}
        self._build_ui()
        self._populate(self._initial_values)

        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.grab_set()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        path_frame = ttk.Frame(self, padding=(10, 10, 10, 0))
        path_frame.pack(fill='x')
        ttk.Label(path_frame, text=f'Config file: {self.config_path}',
                  font=('TkDefaultFont', 8)).pack(anchor='w')

        form_container = ttk.Frame(self, padding=(10, 6, 10, 0))
        form_container.pack(fill='both', expand=True)

        canvas = tk.Canvas(form_container, highlightthickness=0)
        vscroll = ttk.Scrollbar(form_container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side='left', fill='both', expand=True)
        vscroll.pack(side='right', fill='y')

        form = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=form, anchor='nw')
        form.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-event.delta / 120), 'units')
        canvas.bind('<Enter>', lambda _e: canvas.bind_all('<MouseWheel>', _on_mousewheel))
        canvas.bind('<Leave>', lambda _e: canvas.unbind_all('<MouseWheel>'))

        for row, field in enumerate(CONFIG_FIELDS):
            self._build_field_row(form, row, field)
        form.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill='x')
        self.save_button = ttk.Button(btn_frame, text='Save', command=self._on_save)
        self.save_button.pack(side='left')
        ttk.Button(btn_frame, text='Cancel', command=self._on_close).pack(side='left', padx=(6, 0))
        self.run_button = ttk.Button(btn_frame, text='Run', command=self._on_run, state='disabled')
        self.run_button.pack(side='left', padx=(6, 0))

        log_frame = ttk.LabelFrame(self, text='Run Log', padding=6)
        log_frame.pack(fill='both', expand=False, padx=10, pady=(0, 6))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state='disabled', wrap='word')
        self.log_text.pack(fill='both', expand=True)

        self.status_var = tk.StringVar(value='Edit settings, then Save to enable Run.')
        ttk.Label(self, textvariable=self.status_var, padding=(10, 0, 10, 10)).pack(fill='x')

    def _build_field_row(self, form, row, field):
        label_frame = ttk.Frame(form)
        label_frame.grid(row=row, column=0, sticky='w', padx=(0, 6), pady=3)
        ttk.Label(label_frame, text=field['label']).pack(side='left')
        if field.get('help'):
            help_label = ttk.Label(label_frame, text=' (?)', foreground='#3366cc',
                                    cursor='question_arrow')
            help_label.pack(side='left')
            Tooltip(help_label, field['help'])

        if field['kind'] == 'choice':
            var = tk.StringVar()
            widget = ttk.Combobox(form, textvariable=var, values=field['choices'],
                                   state='readonly', width=47)
            widget.grid(row=row, column=1, sticky='ew', pady=3)
        else:
            var = tk.StringVar()
            widget = ttk.Entry(form, textvariable=var, width=50)
            widget.grid(row=row, column=1, sticky='ew', pady=3)

        self._vars[field['key']] = var

        if field['kind'] == 'dir':
            ttk.Button(form, text='Browse...',
                       command=lambda k=field['key']: self._browse_dir(k)
                       ).grid(row=row, column=2, padx=(6, 0), pady=3)

    def _browse_dir(self, key):
        initial = self._vars[key].get() or str(REPO_ROOT)
        selected = filedialog.askdirectory(title='Select a directory', initialdir=initial, parent=self)
        if selected:
            self._vars[key].set(selected)

    # ── Populate / collect ────────────────────────────────────────────────────

    def _populate(self, values):
        for field in CONFIG_FIELDS:
            value = values.get(field['key'])
            if field['kind'] == 'dict':
                text = format_config_value(value) if isinstance(value, dict) else ''
            elif field['kind'] == 'choice':
                text = value if value else field.get('default', '')
            else:
                text = '' if value is None else str(value)
            self._vars[field['key']].set(text)

    def _collect_values(self):
        """Return (values, error) -- error is a user-facing message on invalid input,
        None on success. Does not touch disk."""
        values = {}
        for field in CONFIG_FIELDS:
            text = self._vars[field['key']].get().strip()
            if field['kind'] == 'dict':
                if not text:
                    continue
                try:
                    parsed = ast.literal_eval(text)
                except (ValueError, SyntaxError) as exc:
                    return None, f"{field['label']} must be a valid Python dict: {exc}"
                if not isinstance(parsed, dict):
                    return None, f"{field['label']} must be a Python dict, e.g. {{'RS': 'REFSTAND'}}"
                values[field['key']] = parsed
            else:
                values[field['key']] = text

        missing = [f['label'] for f in CONFIG_FIELDS if f.get('required') and not values.get(f['key'])]
        if missing:
            return None, 'These fields are required:\n' + '\n'.join(missing)
        return values, None

    # ── Directory validation (warn, don't block) ──────────────────────────────

    def _check_dirs(self, values):
        missing_input, missing_output = [], []
        for field in CONFIG_FIELDS:
            if field['kind'] != 'dir':
                continue
            value = values.get(field['key'])
            if not value or Path(value).is_dir():
                continue
            (missing_input if field['key'] == 'dir_source_files' else missing_output).append(
                (field, Path(value)))

        if missing_input:
            listing = '\n'.join(f"  {f['label']}: {p}" for f, p in missing_input)
            messagebox.showwarning(
                'Directory not found',
                f"These directories don't exist yet:\n{listing}\n\n"
                f"They must exist before the pipeline can run.",
                parent=self)

        if missing_output:
            listing = '\n'.join(f"  {f['label']}: {p}" for f, p in missing_output)
            create = messagebox.askyesno(
                'Create output directories?',
                f"These output directories don't exist yet:\n{listing}\n\nCreate them now?",
                parent=self)
            if create:
                for _, p in missing_output:
                    p.mkdir(parents=True, exist_ok=True)

    # ── Save ───────────────────────────────────────────────────────────────────

    def _on_save(self):
        values, error = self._collect_values()
        if error:
            messagebox.showerror('Invalid settings', error, parent=self)
            return

        self._check_dirs(values)

        try:
            write_config_file(self.config_path, values)
        except OSError as exc:
            messagebox.showerror('Save failed', str(exc), parent=self)
            return

        self._saved_values = values
        self.status_var.set(f'Saved to {self.config_path}')
        self.run_button.configure(state='normal')

    # ── Run ────────────────────────────────────────────────────────────────────

    def _on_run(self):
        if self._run_thread is not None and self._run_thread.is_alive():
            return

        self.run_button.configure(state='disabled')
        self.save_button.configure(state='disabled')
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')
        self.status_var.set('Running...')
        self._run_start_ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        self._run_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._run_thread.start()

    def _confirm_from_bg(self, prompt):
        """Thread-safe yes/no bridge: schedules a Tk messagebox on the main thread
        and blocks the calling (background/pipeline) thread until answered."""
        done = threading.Event()
        result = {}

        def _ask():
            result['value'] = messagebox.askyesno('Confirm', prompt, parent=self)
            done.set()

        self.after(0, _ask)
        done.wait()
        return result['value']

    def _run_worker(self):
        redirector = _TextRedirector(self.log_text)
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = redirector
        sys.stderr = redirector
        try:
            handler = run_pipeline(self.config_path, confirm_cb=self._confirm_from_bg)
            n_csv = len(handler.files.get('.csv', []))
            success, summary = True, f'Run complete. CSV files processed: {n_csv}.'
        except Exception:
            success, summary = False, 'Run failed:\n' + traceback.format_exc()
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        self.after(0, self._run_complete, success, summary)

    def _run_complete(self, success, summary):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', '\n' + summary + '\n')
        full_log = self.log_text.get('1.0', 'end')
        self.log_text.configure(state='disabled')

        final_dir = (self._saved_values or {}).get('dir_final_storage')
        log_path = persist_gui_log(full_log, final_dir, timestamp=self._run_start_ts)

        self.log_text.configure(state='normal')
        self.log_text.insert('end', f'\nFull log saved to: {log_path}\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

        self.status_var.set(f"{'Success' if success else 'Failed'} — log: {log_path}")
        self.save_button.configure(state='normal')
        self.run_button.configure(state='normal')

    # ── Close ──────────────────────────────────────────────────────────────────

    def _on_close(self):
        if self._run_thread is not None and self._run_thread.is_alive():
            messagebox.showwarning('Run in progress',
                                    'Wait for the current run to finish before closing.',
                                    parent=self)
            return
        self.grab_release()
        self.destroy()
