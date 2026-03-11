import hobo_qaqc
from pathlib import Path
from datetime import datetime
import zipfile as zp
from numpy import unique
import shutil
import atexit
import ast

__authors__ = 'Greg Cohn'
__version__ = '2.0'

class FileHandling:
    def __init__(self, config='../file_path.config'):
        self.start_date = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.config = self.load_config(config)
        
        self.map_fname2dir = self.config.get('map_fname2dir', {})

        try:
            self.wdir = Path(self.config['dir_local_processing']).resolve()
            self.final_dir = Path(self.config['dir_final_storage']).resolve()
            self.src_dir = Path(self.config['dir_source_files']).resolve()
        except KeyError as e:
            raise SystemExit(f'Error: Missing required configuration: {e} in file_path.config')
        self.time_step = self.config.get('time_step')

        for d in [self.wdir, self.final_dir, self.src_dir]:
            if self._is_spec_char_in_path(d):
                raise SyntaxError(f'Special character used in file path: {d}')

        self.logs = []
        self.files = {'.hobo': [], '.csv': [], '.log': [], 'unk_ext': [], 'sites': []}

        self.data_dir = self.wdir / '_data'
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.proc_dir = self.wdir / '_processed'
        self.proc_dir.mkdir(parents=True, exist_ok=True)

        atexit.register(self.write_log)

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

    @staticmethod
    def _is_spec_char_in_path(path):
        spec_char = '\n\r\t\a\f\v\b\0'
        return any(char in str(path) for char in spec_char)

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
        shutil.copytree(self.src_dir, self.data_dir, dirs_exist_ok=True)

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

    def qaqc_csv(self, time_step=None, units='SI', tz=-8):
        fproc = []
        for f in self.files['.csv']:
            q = hobo_qaqc.HOBOdata(logs=self.logs)
            q.reformat_HOBO_csv(f, self.proc_dir / f.name, tstep=time_step, units=units, tz=tz)
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

    def copy_processed_to_final_dir(self):
        shutil.copytree(self.proc_dir, self.final_dir, dirs_exist_ok=True)

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
        shutil.rmtree(self.data_dir)

        if not any(self.proc_dir.iterdir()):
            self.logs.append(f'Deleting empty processing directory: {self.proc_dir}\n')
            shutil.rmtree(self.proc_dir)
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

    def manage(self, time_step=None, units='SI', tz=-8, final_subdirs=False):
        self.set_log_header()
        self.copy_src_to_wdir()
        self.index_files()

        if time_step is not None:
            self.logs.extend([
                '**********************************',
                f'\nTime step used is {time_step}\nTimestamp syncing is enabled only because a time_step was explicitly provided.\n'
            ])

        start = datetime.now().strftime('%H:%M:%S')
        c_proc, c_count, cproc_count = self.qaqc_csv(time_step=time_step, units=units, tz=tz)
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
            self.copy_processed_to_final_dir()

        # Move any remaining files from proc_dir to final_dir
        for file in self.proc_dir.iterdir():
            if file.is_file():
                shutil.move(str(file), str(self.final_dir / file.name))
                self.logs.append(f"Moved {file.name} to final directory\n")

        self.del_temp_folders()

if __name__ == '__main__':
    mng = FileHandling()
    mng.manage()