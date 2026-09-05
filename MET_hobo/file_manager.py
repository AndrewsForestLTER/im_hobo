if __package__ in (None, ''):
    # Run directly, e.g. `cd MET_hobo; python file_manager.py` -- MET_hobo/ is not
    # on sys.path as a package in this case, so put its parent there instead.
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from MET_hobo import hobo_qaqc
from MET_hobo import hobo_date_summary
from pathlib import Path
from datetime import datetime
import zipfile as zp
from numpy import unique
import shutil
import atexit
import ast
import os
import stat

class FileHandling:
    _EXPECTED_FINAL_DIR_EXTS = {'.csv', '.log'}
    _EXPECTED_FINAL_DIR_SUBDIRS = {'logs', 'TOA5', 'parquet'}
    _TOA5_CONFIG_KEYS = (
        'toa5_station', 'toa5_logger_model', 'toa5_serial', 'toa5_table_name',
        'toa5_os_version', 'toa5_program_name', 'toa5_program_sig',
    )

    def __init__(self, config=None):
        self.start_date = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.config = self.load_config(self._resolve_config_path(config))
        
        self.map_fname2dir = self.config.get('map_fname2dir', {})

        try:
            self.wdir = Path(self.config['dir_local_processing']).resolve()
            self.final_dir = Path(self.config['dir_final_storage']).resolve()
            self.src_dir = Path(self.config['dir_source_files']).resolve()
        except KeyError as e:
            raise SystemExit(f'Error: Missing required configuration: {e} in file_path.config')
        self.time_step = self.config.get('time_step')
        self._confirm_cb = None

        for d in [self.wdir, self.final_dir, self.src_dir]:
            if self._is_spec_char_in_path(d):
                raise SyntaxError(f'Special character used in file path: {d}')

        self.logs = []
        self.files = {'.hobo': [], '.csv': [], '.log': [], 'unk_ext': [], 'sites': []}

        self.data_dir = self.wdir / '_data'
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.proc_dir = self.wdir / '_processed'
        self.proc_dir.mkdir(parents=True, exist_ok=True)

        # Created on demand in qaqc_csv (bulk mode only) so proc_dir stays empty,
        # and therefore deletable by del_temp_folders, when they're unused.
        self.toa5_dir = self.proc_dir / 'TOA5'
        self.parquet_dir = self.proc_dir / 'parquet'

        # Strip the 'toa5_' prefix so these map directly onto export_to_toa5's kwargs.
        self.toa5_kwargs = {
            key[len('toa5_'):]: self.config[key]
            for key in self._TOA5_CONFIG_KEYS if key in self.config
        }

        atexit.register(self.write_log)

    @staticmethod
    def _resolve_config_path(config):
        """Resolve the file_path.config to load, independent of the caller's cwd.

        Checked in order:
        1. An explicit path, if given.
        2. The IM_HOBO_CONFIG environment variable, if set.
        3. file_path.config in the current directory.
        4. file_path.config in the repository root (two levels up from this file),
           so this resolves the same way whether run as `python -m MET_hobo.file_manager`
           from the repo root or as `python file_manager.py` from MET_hobo/.
        """
        if config is not None:
            return config

        env_config = os.environ.get('IM_HOBO_CONFIG')
        if env_config:
            return env_config

        repo_root = Path(__file__).resolve().parent.parent
        candidates = [Path.cwd() / 'file_path.config', repo_root / 'file_path.config']
        for candidate in candidates:
            if candidate.exists():
                return candidate

        tried = '\n  '.join(str(c) for c in candidates)
        raise FileNotFoundError(
            f'No file_path.config found. Tried:\n  {tried}\n\n'
            f'Set the IM_HOBO_CONFIG environment variable, pass an explicit path via '
            f'FileHandling(config=...) or --config, or copy file_path.config.example '
            f'to one of the paths above and edit it.'
        )

    @staticmethod
    def load_config(config_path):
        config = {}
        with open(config_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    try:
                        # Try to evaluate as a Python literal
                        config[key] = ast.literal_eval(value)
                    except (ValueError, SyntaxError):
                        # If it's not a Python literal, treat it as a string
                        config[key] = value.strip('"').strip("'")
        return config

    def _confirm(self, prompt):
        """Ask a yes/no question.

        Uses self._confirm_cb if one was passed to manage() -- e.g. a GUI's
        thread-safe bridge to a Tk messagebox -- otherwise falls back to a
        console y/N prompt. Without this indirection, a GUI run landing on a
        console input() call would hang its background thread forever.
        """
        if self._confirm_cb is not None:
            return bool(self._confirm_cb(prompt))
        answer = input(f'{prompt} [y/N]: ').strip().lower()
        return answer == 'y'

    @staticmethod
    def _is_spec_char_in_path(path):
        spec_char = '\n\r\t\a\f\v\b\0'
        return any(char in str(path) for char in spec_char)

    @staticmethod
    def _rmtree(path):
        """Remove a directory tree, handling Windows read-only files."""
        def _on_error(func, p, exc_info):
            os.chmod(p, stat.S_IWRITE)
            func(p)
        shutil.rmtree(path, onerror=_on_error)

    def _get_projname(self, f):
        fname2dir = self.map_fname2dir
        name = Path(f).stem.partition('_')[0].partition(' ')[0]
        return next((fname2dir[k] for k in fname2dir if k in name), 'UnknownProject')

    def set_log_header(self):
        logs = [
            'Process CSV output from HOBOWARE for time zone, timestep, and units\n',
            '=====================================================================\n',
            'MET_hobo module\n',
            f'Date: {self.start_date}\n'
        ]
        self.logs.extend(logs)

    def copy_src_to_wdir(self):
        if self.data_dir.exists():
            self._rmtree(self.data_dir)
        shutil.copytree(self.src_dir, self.data_dir)

    def index_files(self):
        for path in self.data_dir.rglob('*'):
            if path.is_file():
                suffix = path.suffix.lower()
                if suffix in ('.csv', '.hobo', '.log'):
                    self.files[suffix].append(path)
                else:
                    self.files['unk_ext'].append(path)
                
                if suffix == '.csv':
                    site = path.stem.partition('_')[0].partition(' ')[0]
                    self.files['sites'].append(site)

        self.files['sites'] = list(unique(self.files['sites']))

    def qaqc_csv(self, time_step=None, units='SI', tz=-8, final_subdirs=False):
        # TOA5/parquet writers are scoped to bulk mode only for now: final_subdirs
        # routes output by project/site via copy_selected_to_site_dir, which globs
        # proc_dir's top level and doesn't know about these nested output dirs.
        if not final_subdirs:
            self.toa5_dir.mkdir(parents=True, exist_ok=True)
            self.parquet_dir.mkdir(parents=True, exist_ok=True)

        fproc = []
        for f in self.files['.csv']:
            q = hobo_qaqc.HOBOdata(logs=self.logs)
            q.reformat_HOBO_csv(f, self.proc_dir / f.name, tstep=time_step, units=units, tz=tz)
            if not final_subdirs:
                sitecode = hobo_date_summary.extract_sitecode(f.name)
                q.export_to_toa5(self.toa5_dir / f'{f.stem}.dat', sitecode=sitecode, **self.toa5_kwargs)
                q.export_to_parquet(self.parquet_dir / f'{f.stem}.parquet', sitecode=sitecode)
            fproc.append(str(f) + '\n')

        return fproc, len(self.files['.csv']), len(fproc)

    def zip_hobo_files(self):
        zproc = []
        for f in self.files['.hobo']:
            site = f.stem.partition('_')[0]
            fzip = self.proc_dir / f'{site}_{self.start_date}.zip'
            with zp.ZipFile(fzip, 'a') as zhobo:
                zhobo.write(f, f.name, compress_type=zp.ZIP_DEFLATED)
            zproc.extend([str(f) + '\n', str(fzip) + '\n'])

        return zproc, len(self.files['.hobo']), len(zproc) // 2

    def _unexpected_final_dir_contents(self):
        """Return entries in final_dir that aren't plain .csv/.log files or a logs/ subdir."""
        unexpected = []
        for entry in self.final_dir.iterdir():
            if entry.name.startswith('.'):
                unexpected.append(entry)
            elif entry.is_dir():
                if entry.name not in self._EXPECTED_FINAL_DIR_SUBDIRS:
                    unexpected.append(entry)
            elif entry.suffix.lower() not in self._EXPECTED_FINAL_DIR_EXTS:
                unexpected.append(entry)
        return unexpected

    def _clear_final_dir(self, force=False):
        """Clear final_dir, prompting for confirmation if it holds unexpected content.

        final_dir is user-configurable (file_path.config), unlike data_dir/proc_dir,
        so an rmtree here can silently destroy unrelated content if misconfigured.
        Returns True if final_dir was cleared, False if the clear was skipped.
        """
        unexpected = self._unexpected_final_dir_contents()
        if unexpected and not force:
            listing = '\n'.join(f'  {p}' for p in sorted(unexpected, key=str))
            proceed = self._confirm(
                f'The final output directory contains unexpected content that will be '
                f'permanently deleted:\n{listing}\n\n'
                f'Proceed with clearing {self.final_dir}?'
            )
            if not proceed:
                self.logs.append(
                    f'WARNING: Declined to clear final output directory {self.final_dir}; '
                    f'unexpected content present: {[str(p) for p in unexpected]}. '
                    f'Final directory NOT cleared or updated this run.\n'
                )
                return False

        self._rmtree(self.final_dir)
        self.logs.append(f'Cleared final output directory: {self.final_dir}\n')
        return True

    def copy_processed_to_final_dir(self, force=False):
        if self.final_dir.exists():
            if not self._clear_final_dir(force=force):
                return
        shutil.copytree(self.proc_dir, self.final_dir)

    def copy_selected_to_site_dir(self, file_list, subdir, loc):
        fproc = []
        for s in file_list:
            prj = self._get_projname(s)
            storage = self.final_dir / subdir if Path(s).is_file() else self.final_dir / prj / s / subdir
            storage.mkdir(parents=True, exist_ok=True)

            for file in Path(loc).glob(f'{Path(s).name}*'):
                shutil.copy2(file, storage)
                fproc.append(str(file) + '\n')

        return fproc

    def del_temp_folders(self):
        self.logs.extend([
            '\n\nDeleting Temporary DIR from Working DIR\n************************************\n',
            f'{self.data_dir}\n'
        ])
        self._rmtree(self.data_dir)

        if not any(self.proc_dir.iterdir()):
            self.logs.append(f'Deleting empty processing directory: {self.proc_dir}\n')
            self._rmtree(self.proc_dir)
        else:
            self.logs.append(f'WARNING: {self.proc_dir} is not empty. Some files may not have been processed or moved.\n')

    def del_files_frm_srcdir(self):
        if self.src_dir == self.final_dir:
            self.logs.append('WARNING!!!: Source directory is same as final directory.\nABORT DIRECTORY CLEAN\n')
            return []

        f_wipe = []
        for path in self.src_dir.rglob('*'):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            f_wipe.append(str(path) + '\n')

        return f_wipe

    def write_log(self):
        log_dir = self.final_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f'hobo_qaqc_{self.start_date}.log'
        log_file.write_text(''.join(self.logs))

    @staticmethod
    def _log_chg(proc, start, end, dir_frm, dir_to, tot_cnt, chg_cnt, f_list):
        log = [
            f"\n\n----------------------------\nStart {proc} - {start}\n----------------------------\n"
            f"---------Read from {dir_frm}\n"
            f"---------Output to  {dir_to}\n"
            f"--------- {tot_cnt} files total\n"
            f"--------- {chg_cnt} files processed\n"
        ]
        log.extend(f_list)
        log.append(f'\n----------------------------\nEnd {proc}- {end}\n----------------------------\n')
        return log

    def _run_dedupe(self, final_subdirs):
        """Run hobo_date_summary dedup against final_dir, per dedupe_mode in config."""
        dedupe_mode = self.config.get('dedupe_mode', 'off')
        if dedupe_mode == 'off':
            return

        if final_subdirs:
            self.logs.append(
                'Dedupe skipped: final_subdirs=True is not supported by dedupe_mode.\n'
            )
            return

        if dedupe_mode == 'prompt':
            if not self._confirm(f'Run dedupe on {self.final_dir}?'):
                self.logs.append('Dedupe skipped: user declined at prompt.\n')
                return
        elif dedupe_mode != 'auto':
            self.logs.append(f"Dedupe skipped: unrecognized dedupe_mode '{dedupe_mode}'.\n")
            return

        dedupe_output = self.config.get('dir_dedupe_output')

        start = datetime.now().strftime('%H:%M:%S')
        rows = hobo_date_summary.summarize_directories([self.final_dir])
        log_entries = hobo_date_summary.deduplicate_and_write(rows, dedupe_output=dedupe_output)
        end = datetime.now().strftime('%H:%M:%S')

        out_dir = hobo_date_summary.build_dedupe_output_path(self.final_dir, configured=dedupe_output)
        truncated = sum(1 for e in log_entries if e['records_removed'] > 0)
        total_removed = sum(e['records_removed'] for e in log_entries)
        f_list = [f"{e['filename']}: {e['action']} ({e['records_removed']} removed)\n" for e in log_entries]

        self.logs.extend(self._log_chg('dedupe', start, end, self.final_dir, out_dir, len(log_entries), truncated, f_list))
        self.logs.append(f'--------- {total_removed} duplicate record(s) removed across all files\n')

    def manage(self, time_step=None, units='SI', tz=-8, final_subdirs=False, force_clear=False,
               confirm_cb=None):
        """Run the full QAQC pipeline.

        confirm_cb, if given, is a callable(prompt: str) -> bool used in place of a
        console y/N input() for any confirmation the pipeline needs (clearing a final
        output directory with unexpected content, dedupe_mode="prompt"). Pass a
        thread-safe bridge to a GUI dialog here when calling manage() off the main
        thread -- see _confirm().
        """
        self._confirm_cb = confirm_cb
        self.set_log_header()
        self.copy_src_to_wdir()
        self.index_files()

        if time_step is not None:
            self.logs.extend([
                '**********************************',
                f'\nTime step used is {time_step}\nTimestamp syncing is enabled only because a time_step was explicitly provided.\n'
            ])

        start = datetime.now().strftime('%H:%M:%S')
        c_proc, c_count, cproc_count = self.qaqc_csv(time_step=time_step, units=units, tz=tz, final_subdirs=final_subdirs)
        end = datetime.now().strftime('%H:%M:%S')
        self.logs.extend(self._log_chg('csv reformat', start, end, self.data_dir, self.proc_dir, c_count, cproc_count, c_proc))

        self.files['unk_ext'].extend(self.files['.hobo'])

        self.logs.append('\n\n Start copy  DATA TO FINAL STORAGE\n***********************************************\n\n')

        if final_subdirs:
            _ = self.copy_selected_to_site_dir(self.files['sites'], '_bulk_exp_clean', self.proc_dir)
            if self.files['unk_ext']:
                self.logs.append('\n\n Start copy  UNRECOGNIZED FILE .EXT\n***********************************************\n\n')
                fproc = self.copy_selected_to_site_dir(self.files['unk_ext'], 'UNK_FILE', self.data_dir)
                self.logs.extend(fproc)

            if self.files['.log']:
                fproc = self.copy_selected_to_site_dir(['.log'], 'logs', self.data_dir)
                self.logs.extend(fproc)
        else:
            self.copy_processed_to_final_dir(force=force_clear)

        # Move any remaining files or subdirectories (e.g. TOA5/, parquet/) from
        # proc_dir to final_dir, so proc_dir ends up empty for del_temp_folders.
        for entry in self.proc_dir.iterdir():
            dest = self.final_dir / entry.name
            if entry.is_dir() and dest.exists():
                self._rmtree(dest)
            shutil.move(str(entry), str(dest))
            self.logs.append(f"Moved {entry.name} to final directory\n")

        self._run_dedupe(final_subdirs)
        self.del_temp_folders()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--yes', '--force', dest='force', action='store_true',
        help='Skip the confirmation prompt when clearing an unexpected final output directory'
    )
    parser.add_argument(
        '--config', default=None,
        help='Path to file_path.config. Default: the IM_HOBO_CONFIG environment '
             'variable, then file_path.config in the current directory, then in '
             'the repository root.'
    )
    args = parser.parse_args()

    mng = FileHandling(config=args.config)
    mng.manage(force_clear=args.force)