import hobo_qaqc, subprocess
# possible change to os.name to decrease dependencies
from sys import platform
from os import listdir, makedirs, remove
from os.path import isdir, basename, isfile, abspath
from datetime import datetime
import zipfile as zp
from numpy import unique
from shutil import rmtree

class FileHandling:
    """

    """
    def __init__(self):
        """

        :return:
        """
        self.start_date = datetime.now().strftime('%Y%m%d_%H%M%S')

        # load config file as one formatted string
        # partial path is a weak point and assumes that pwd is ./MET_hobo/MET_hobo
        with open('../file_path.config') as f:
            lines = f.read()

        # compile file into pyc (essentially a local .pyc)
        pyc = compile(lines, '<string>', 'exec')
        # use exec as function for forward compatibility with 3.x (2.x exec can be a statement)
        # this process improves speed %12
        exec(pyc)

        # save directory paths to class instance
        wdir = dir_local_processing
        self.wdir = wdir
        self.final_dir = dir_final_storage
        self.src_dir = dir_source_files

        self.map_fname2dir = map_fname2dir

        self.logs = []

        self.files = {'.hobo':[],
                      '.csv':[],
                      '.log':[],
                      'unk_ext':[],
                      'sites':[]}

        OS = platform
        if 'win' in OS:
            # options mov: cuts, mir: copies, TEE: prints to screen, e: includes sub-dir, XX: excludes dir
            self.copy = {'cmd':'robocopy', 'opt_mirror_all':'/MIR /TEE /e',
                         'opt_cut_files':'/mov /TEE /XX'}
            self.sep = '\\'

        data_dir = wdir + '_data/'
        self._mkdirs_exist_ok(data_dir)
        self.data_dir = data_dir

        processed = wdir + '_processed/'
        self._mkdirs_exist_ok(processed)
        self.proc_dir = processed


    def _mkdirs_exist_ok(self, dpath):
        """
        ..To Do::
        In update to >=3.2, mkdirs(exist_ok=True)
        """
        makedirs(dpath) if not isdir(dpath) else False

    def _get_projname(self, f):
        """

        :param f:
        :return:
        """
        fname2dir = self.map_fname2dir
        name_list = [fname2dir[k] for k in fname2dir.keys() if k in f.split('_')[0]]
        return name_list[0] if name_list else 'UnknownProject'


    def set_log_header(self):
        """

        :return:
        """
        logs = ['Process CSV output from HOBOWARE for time zone, timestep, and units\n',
                '=====================================================================\n',
                'Date: %s\n'%self.start_date]
        self.logs.extend(logs)


    def copy_to_wdir(self):
        """
        Copies source files to local working directory using OS specifc DOS, bash, or shell command. Results are output
         to log file.
        :return:
        """
        cp = self.copy

        # Copy files from server to local machine (or to processing folder)
        cmd = '%s %s %s %s'%(cp['cmd'], self.src_dir, self.data_dir, cp['opt_mirror_all'])
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.logs.extend(proc.communicate())


    def index_files(self):
        '''

        :return:
        '''
        fdata = self.data_dir
        index_files = self.files
        sep = self.sep
        data_files = listdir(fdata)

        sites = []
        for f in data_files:
            # initially, file list does not contain any path information. As full file paths are appended to the list
            # file names have full paths and do not need additional path information
            if isdir(fdata + f) or isdir(f):
                # add files from subdirectories
                f_path = f if isdir(f) else fdata + f
                oswalk = [f_path + sep + f1 for f1 in listdir(f_path)]
                data_files.extend(oswalk)
            else:
                # strip file path and extension, and read first segment from file name. E.g. RS05 from path/RS05_*.zip
                sites.append(f.split(sep)[-1].split('_')[0].split('.')[0])
                fp = abspath(fdata + f if not isfile(f) else f)
                if f.endswith('.csv'):
                    index_files['.csv'].append(fp)
                elif f.endswith('.hobo'):
                    index_files['.hobo'].append(fp)
                elif f.endswith('.log'):
                    index_files['.log'].append(fp)
                else:
                    index_files['unk_ext'].append(fp)

        index_files['sites'] = unique(sites)
        self.files = index_files


    def qaqc_csv(self):
        """

        :return:
        """
        # Reformat and QAQC all CSV files
        proc_dir = self.proc_dir

        fcsv = self.files['.csv']
        fproc = []
        for f in fcsv:
            q = hobo_qaqc.HOBOdata()
            q.reformat_HOBO_csv(f, proc_dir + basename(f))
            q = None

            fproc.append(f + '\n')

        fproc_count = fproc.__len__()
        fdir_count = fcsv.__len__()
        return fproc, fdir_count, fproc_count


    def zip_hobo_files(self):
        """
        Loop through list, which includes sub-directories, and append to archive in _processed folder
        then use glob.glob* to copy all of a site at once
        :return:
        """
        proc_dir = self.proc_dir
        sep = self.sep
        date = self.start_date

        # is it faster to loop through a list of files and append to .zip every time OR
        # is it faster to use glob.glob('*') to generate a list of .hobo's for each site and make a zipfile once
        fhobo = self.files['.hobo']
        zproc = []
        for f in fhobo:
            site = f.split(sep)[-1].split('_')[0].split('.')[0]
            fname = basename(f)

            fzip = proc_dir + site + '_' + date + '.zip'
            with zp.ZipFile(fzip, 'a') as zhobo:
                zhobo.write(f, fname, compress_type=zp.ZIP_DEFLATED)

            zproc.append(f + '\n')
            zproc.append(fzip + '\n')

        zproc_count = zproc.__len__()
        fhobo_count = fhobo.__len__()
        return zproc, fhobo_count, zproc_count


    def copy_to_final_dir(self, file_list, subdir, loc):
        """

        :param file_list:
        :param subdir:
        :param loc:
        :return:
        """

        fnc_get_prj = self._get_projname
        fnc_mkdirs_exists = self._mkdirs_exist_ok
        cp = self.copy

        fin_dir = self.final_dir
        sep = self.sep

        logs = []
        fproc = []
        for s in file_list:
            prj = fnc_get_prj(s)

            storage = fin_dir + sep + prj + sep + s + subdir
            fnc_mkdirs_exists(storage)

            # Cut files from local machine (or processing folder) to final storage (server)
            cmd = '%s %s %s %s %s'%(cp['cmd'], loc, storage, '"%s*"'%(s), cp['opt_cut_files'])
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logs.extend(proc.communicate())

            fproc.append(s + '\n')

        self.logs.extend(logs)
        return fproc

    def del_temp_folders(self):
        '''
        This is to wipe temporary processing folders in the working directory. The convention maintained by this module
        is that all temp folders have the "_" prefix

        ..Warning::
            This uses destructive methods which will erase any and all contents of the target directory and any sub-
            directories within.

            shutil.rmtree()

        :return:
        '''

        self.logs.extend(['\n\nDeleting Temporary DIR from Working DIR\n************************************\n',
                          '%s\n%s\n' % (self.proc_dir, self.data_dir)])
        rmtree(self.proc_dir)
        rmtree(self.data_dir)

    def del_files_frm_srcdir(self):
        '''
        This is to wipe all files from the src_dir, defined in file_path.config as dir_source_files. All files and sub-
        folders in this directory will be wiped.

        ..Warning::
            This uses destructive methods which will erase any and all contents of the target directory and any sub-
            directories within.

            shutil.rmtree()

        :return:
        '''
        sdir = self.src_dir

        if sdir == self.final_dir:
            self.logs.extend('WARNING!!!: Source direcotry is same as final directory. Directory clean aborted\n')

        f_wipe = []
        for f in listdir(sdir):
            if isfile(sdir + f):
                remove(sdir + f)
            elif isdir(sdir + f):
                rmtree(sdir + f)

            f_wipe.append(f + '\n')

        return f_wipe

    def write_log(self):
        """

        :return:
        """
        wdir = self.wdir
        date = self.start_date
        logs = self.logs

        self._mkdirs_exist_ok(wdir + '/logs')

        flog = wdir + '/logs/hobo_qaqc_' + date + '.log'
        with open(flog, 'a') as f:
            f.writelines(logs)


    def manage(self):
        """

        :return:
        """

        def log_chg(proc, start, end, dir_frm, dir_to, tot_cnt, chg_cnt, f_list):
            head ="""\n\n----------------------------\nStart %s - %s\n----------------------------
            ---------Read from %s
            ---------Ouput to  %s
            --------- %d files total
            --------- %d files processed
            """

            tail = '\n\n----------------------------\nEnd %s- %s\n----------------------------\n'
            log = [head%(proc, start, dir_frm, dir_to, tot_cnt, chg_cnt)]
            log.extend(f_list)
            log.extend(tail%(proc, end))
            return log

        self.set_log_header()
        self.copy_to_wdir()
        self.index_files()

        start = datetime.now().strftime('%H:%M:%S')
        # QAQC .csv files
        c_proc, c_count, cproc_count = self.qaqc_csv()
        end = datetime.now().strftime('%H:%M:%S')
        self.logs.extend(log_chg('csv reformat', start, end, self.data_dir, self.proc_dir, c_count, cproc_count, c_proc))

        start = datetime.now().strftime('%H:%M:%S')
        # ZIP .hobo files
        h_proc, h_count, hproc_count = self.zip_hobo_files()
        end = datetime.now().strftime('%H:%M:%S')
        self.logs.extend(log_chg('archive .hobo in ZIP',  start, end, self.data_dir, self.proc_dir, h_count, hproc_count, h_proc))

        self.logs.append('\n\n Start copy  DATA TO FINAL STORAGE\n***********************************************\n\n')
        _ = self.copy_to_final_dir(self.files['sites'], '/hobo', self.proc_dir)

        self.logs.append('\n\n Start copy  UNRECOGNIZED FILE .EXT\n***********************************************\n\n')
        if self.files['unk_ext'] != []:
            fproc = self.copy_to_final_dir(self.files['unk_ext'], '/UNK_FILE', self.data_dir)
            self.logs.extend(fproc)
        else:
            self.logs.append('NONE')

        if self.files['.log'] != []:
            fproc = self.copy_to_final_dir(['log'], '', self.data_dir)
            self.logs.extend(fproc)

        # Clean directories
        self.del_temp_folders()
        start = datetime.now().strftime('%H:%M:%S')
        f_wipe = self.del_files_frm_srcdir()
        end = datetime.now().strftime('%H:%M:%S')
        warn = '!!WARNING!! WIPING ORIGINAL DATA DIRECTORY\n************************************\
                \n--------- Files/Dir Wiped %s\n' % f_wipe.__len__()
        self.logs.extend(warn)
        self.logs.extend(f_wipe)


        # Write log
        self.write_log()


if __name__ == '__main__':
    mng = FileHandling()
    mng.manage()
    mng.write_log()
