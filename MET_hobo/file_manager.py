"""
This module preforms QAQC methods in a batch. Methods were developed to process csv files created by HOBO sensors at
`meteorological sites`_ on the HJ Andrews experimental forest. It also preforms other file storage and management
functions. For a
specified directory, it processes all files and creates a directory of new, processed csv files.

QAQC methods are imported from :meth:`hobo_qaqc.HOBOdata.reformat_HOBO_csv`.

When module is called :meth:`FileHandling.manage` is executed.

This module is designed to minimize any read/write times by copying all files locally, preforming all processes, and
then transferring files to final directories. This is ideal with external or network drives, but if all directories are\
 local, it will create a final directory which duplicates file names from the source directory.

.. _`meteorological sites`: https://andrewsforest.oregonstate.edu/research/infrastructure/climate
"""

import hobo_qaqc, subprocess
from sys import platform
from os import listdir, makedirs, remove
from os.path import isdir, basename, isfile, abspath
from datetime import datetime
import zipfile as zp
from numpy import unique
from shutil import rmtree
import atexit

class FileHandling:
    """
    Processes all files in assigned directory for timezone, units, and timestep sync, and converts values where
    necessary. Contains methods for archiving using .zip, wiping directories after processing, and adding to
    existing directory structure: ./<FileArchive>/<Project>/<Site>.

    .. Warning::
        Executes ./MET_hobo/file_path.config as Python file and saves variables to class object.

    .. todo::
        possible change from sys.platform to os.name to decrease package dependencies

        possible change from shutil.rmtrees to os.remove os.rmdir
    """
    def __init__(self):
        """
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

        self.time_step = time_step

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
        else:
            raise OSError('This module does not support %s at this time\n'%OS)

        data_dir = wdir + '_data/'
        self._mkdirs_exist_ok(data_dir)
        self.data_dir = data_dir

        processed = wdir + '_processed/'
        self._mkdirs_exist_ok(processed)
        self.proc_dir = processed

        # whenever, the process exits (errors/complete) write log
        atexit.register(self.write_log)


    def _mkdirs_exist_ok(self, dpath):
        """
        Private function. Obsolete in Python >=3.2. Create directory if does not exist.

        :param dpath: str. Absolute path to directory.

        .. todo::
        In update to >=3.2, mkdirs(exist_ok=True)
        """
        makedirs(dpath) if not isdir(dpath) else False

    def _get_projname(self, f):
        """
        Private function. Use map_fname2dir (from file_path.config) to key filename to project name
        :param f: str. Filename
        :return: str. Project name
        """
        fname2dir = self.map_fname2dir
        name_list = [fname2dir[k] for k in fname2dir.keys() if k in f.split('_')[0]]
        return name_list[0] if name_list else 'UnknownProject'


    def set_log_header(self):
        """
        Create header for log file. Assigns first items to list self.logs.
        """
        logs = ['Process CSV output from HOBOWARE for time zone, timestep, and units\n',
                '=====================================================================\n',
                'MET_hobo module\n',
                'Date: %s\n'%self.start_date]
        self.logs.extend(logs)


    def copy_to_wdir(self):
        """
        Copies source files to local working directory using OS specifc DOS, bash, or shell command. Results are output
        to log file.
        """
        cp = self.copy

        # Copy files from server to local machine (or to processing folder)
        cmd = '%s %s %s %s'%(cp['cmd'], self.src_dir, self.data_dir, cp['opt_mirror_all'])
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.logs.extend(proc.communicate())


    def index_files(self):
        '''
        Identify files in source directory. Create list of .hobo, .csv, .log files, and any other file type encountered.

        Identify site as any prefix to the left of "_" in filename and generate a list of unique sites.
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


    def qaqc_csv(self, time_step=None, units='SI', tz=-8):
        """
        Attempt to QAQC all csv files for timezone, timestep sync, and units.

        For list of .csv files generated by :meth:`index_files`, call :meth:`hobo_qaqc.HOBOdata.reformat_HOBO_csv`.

        :return: list. strings of filenames processed with \\\\n at end.
        :return: int. number of csv files
        :return: int. number of files processed
        """
        if time_step is None:
            time_step = self.time_step
        # Reformat and QAQC all CSV files
        proc_dir = self.proc_dir

        fcsv = self.files['.csv']
        fproc = []
        for f in fcsv:
            q = hobo_qaqc.HOBOdata()
            q.reformat_HOBO_csv(f, proc_dir + basename(f), tstep=time_step, units=units, tz=tz)
            q = None

            fproc.append(f + '\n')

        fproc_count = fproc.__len__()
        fdir_count = fcsv.__len__()
        return fproc, fdir_count, fproc_count


    def zip_hobo_files(self):
        """
        Collect all files with .hobo extension and write to a zip file in the temp directory _processed.

        Naming convetion is <site>_<today's date>.zip, where site is any filename prefix to the left of "_".

        For list of .hobo files generated by :meth:`index_files`

        :return: List of strings of each filename and it's zipped filename with a \\\\n at the end
        :return: int. Count of hobo files
        :return: int. Count of zipped files
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
        Call OS specific system command to  copy from temporary working directory to final storage. Selects files by
        site using wildcard selection.

        **Example:**
            RS12*

        :param file_list: List of str to select files from. `Example: ['RS12','RS04'] copies files 'RS12*' and 'RS04*'`
        :param subdir: str. Destination subdirectory within final storage directory. Files are moved to here.
        :param loc: str. Directory where files are currently located.
        :return: List of strings of each filename copied to the final directory
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

            '''
            .. Warning::
                The following line was edited per bitbucket issue #10_ to create a simpler file storage where file
                movement is more manually controlled.

            .. _#10 : https://bitbucket.org/hjandrews/met_hobo/issues/10/task-request-simplify-file-management
            storage = fin_dir + sep + prj + sep + s + subdir
            '''
            storage = fin_dir + sep + subdir
            fnc_mkdirs_exists(storage)

            # Cut files from local machine (or processing folder) to final storage (server)
            cmd = '%s %s %s %s %s'%(cp['cmd'], loc, storage, '"%s*"'%(basename(s)), cp['opt_cut_files'])
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logs.extend(proc.communicate())

            fproc.append(s + '\n')

        self.logs.extend(logs)
        return fproc

    def del_temp_folders(self):
        '''
        This is to wipe temporary processing folders in the working directory. The convention maintained by this module
        is that all temp folders have the "_" prefix

        If any files are still in _processed, and have not been copied to a final storage directory, deletion of this
        directory will be aborted.

        .. Warning::
            This uses destructive methods which will erase any and all contents of the target directory and any sub-
            directories within.

            shutil.rmtree()
        '''
        output = self.proc_dir
        self.logs.extend(['\n\nDeleting Temporary DIR from Working DIR\n************************************\n',
                          '%s\n%s\n' % (output, self.data_dir)])
        rmtree(self.data_dir)

        if listdir(output) == []:
            # All processed files output from MET_hobo.hobo_qaqc should be transferred to final storage.
            rmtree(output)
        else:
            self.logs.append('!!!WARNING!!! %s is not empty!\nABORT DIRECTORY CLEAN\n'%output)

    def del_files_frm_srcdir(self):
        '''
        Wipe all files from the src_dir, defined in file_path.config as dir_source_files. All files and sub-
        folders in this directory will be wiped.

        If source directory and final directory are the same, this process will abort.

        .. Warning::
            This uses destructive methods which will erase any and all contents of the target directory and any sub-
            directories within.

            shutil.rmtree()

        :return: List of strings of each filename wiped from the source directory
        '''
        sdir = self.src_dir
        sep = self.sep

        if sdir == self.final_dir:
            self.logs.extend('WARNING!!!: Source direcotry is same as final directory.\nABORT DIRECTORY CLEAN\n')
            return

        f_wipe = []
        for f in listdir(sdir):
            f_name = sdir + sep + f
            if isfile(f_name):
                remove(f_name)
            elif isdir(f_name):
                rmtree(f_name)
            else:
                f = None

            f_wipe.append(f + '\n')

        return f_wipe

    def write_log(self):
        """
        Write log to file. <final storage directory>//logs//hobo_qaqc_<date>.log.

        Log is a list of strings until this function is called.
        """
        fin_dir = self.final_dir
        date = self.start_date
        logs = self.logs

        self._mkdirs_exist_ok(fin_dir + '/logs')

        flog = fin_dir + '/logs/hobo_qaqc_' + date + '.log'
        with open(flog, 'a') as f:
            f.writelines(logs)

    def _log_chg(self, proc, start, end, dir_frm, dir_to, tot_cnt, chg_cnt, f_list):
        """
        Private function. Creates a list of strings to add bunches of files to a log
        :param proc: str. What process was preformed
        :param start: start time
        :param end: end time
        :param dir_frm: directory of source files
        :param dir_to: directory of final files
        :param tot_cnt: count of all files
        :param chg_cnt: count of manipulated files
        :param f_list: list of file names or file paths
        :return: list of strings
        """
        log = [
            """\n\n----------------------------\nStart {proc} - {start}\n----------------------------\
            \n---------Read from {dir_frm}\
            \n---------Ouput to  {dir_to}\
            \n--------- {tot_cnt} files total\
            \n--------- {chg_cnt} files processed\
            \n""".format(**locals())
              ]

        log.extend(f_list)
        tail = '\n----------------------------\nEnd %s- %s\n----------------------------\n'
        log.append(tail%(proc, end))
        return log


    def manage(self, time_step=None, units='SI', tz=-8):
        """
        Execute file managment.

            #. Copy files to working directory (./_data).
            #. Create list of .csv, .hobo, and .logs files in working directory.
            #. Attempt to preform QAQC on all .csv files and transfer to ./_processed.
            #. Create a .zip file for all .hobo files from each site. Disabled per bitbucket `issue #10`_ .
            #. Copy all files with .csv, .log, and unknown extension to final storage.
            #. Delete temporary folders in working directory.
            #. Wipe original source directory. This directory contains files where QAQC was not preformed. Disabled per \
            bitbucket `issue #10`_ .
            #. Write log file.

        .. _`issue #10`: https://bitbucket.org/hjandrews/met_hobo/issues/10/task-request-simplify-file-management
        """

        # Copy files to a working directory and index file types and study sites
        self.set_log_header()
        self.copy_to_wdir()
        self.index_files()

        # Run QAQC and log results
        if time_step is not None:
            self.logs.extend(['**********************************',
                '\nTime step used is %s\nTime step in config file was (%s) and was overrided at \
            terminal\n'% (time_step, self.time_step)])
        start = datetime.now().strftime('%H:%M:%S')
        c_proc, c_count, cproc_count = self.qaqc_csv(time_step=time_step, units=units, tz=tz)
        end = datetime.now().strftime('%H:%M:%S')
        self.logs.extend(self._log_chg('csv reformat', start, end, self.data_dir, self.proc_dir, c_count, cproc_count, c_proc))

        '''
        .. Warning::
            The following feature was disabled per bitbucket issue #10_ to create a simpler file storage where file
            movement is more manually controlled.

        .. _#10 :https://bitbucket.org/hjandrews/met_hobo/issues/10/task-request-simplify-file-management

        # ZIP any .hobo files into an archive
        start = datetime.now().strftime('%H:%M:%S')
        h_proc, h_count, hproc_count = self.zip_hobo_files()
        end = datetime.now().strftime('%H:%M:%S')
        self.logs.extend(self._log_chg('archive .hobo in ZIP',  start, end, self.data_dir, self.proc_dir, h_count, hproc_count, h_proc))
        '''
        self.files['unk_ext'].extend(self.files['.hobo'])

        # Copy files to final storage location
        self.logs.append('\n\n Start copy  DATA TO FINAL STORAGE\n***********************************************\n\n')
        _ = self.copy_to_final_dir(self.files['sites'], '_bulk_exp_clean', self.proc_dir)

        # Store any files that are not recognized as data files
        if self.files['unk_ext'] != []:
            self.logs.append(
                '\n\n Start copy  UNRECOGNIZED FILE .EXT\n***********************************************\n\n')
            fproc = self.copy_to_final_dir(self.files['unk_ext'], 'UNK_FILE', self.data_dir)
            self.logs.extend(fproc)

        if self.files['.log'] != []:
            fproc = self.copy_to_final_dir(self.files['.log'], 'logs', self.data_dir)
            self.logs.extend(fproc)

        # Clean directories
        self.del_temp_folders()
        '''
        .. Warning::
            The following feature was disabled per bitbucket issue #10_ to create a simpler file storage where file
            movement is more manually controlled.

        .. _#10 : https://bitbucket.org/hjandrews/met_hobo/issues/10/task-request-simplify-file-management
        start = datetime.now().strftime('%H:%M:%S')
        f_wipe = self.del_files_frm_srcdir()
        end = datetime.now().strftime('%H:%M:%S')
        warn = '!!WARNING!! WIPING ORIGINAL DATA DIRECTORY\n************************************\
                \n--------- Files/Dir Wiped %s\n' % f_wipe.__len__()
        self.logs.extend(warn)
        self.logs.extend(f_wipe)
        '''

if __name__ == '__main__':
    mng = FileHandling()
    mng.manage()
