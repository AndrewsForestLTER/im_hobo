import sys
from os import listdir
from os.path import join, basename
import atexit
from datetime import datetime

sys.path.append('../MET_hobo')
import hobo_qaqc
import file_manager
#from context import MET_hobo


class Tests(object):
    def __init__(self, meths, obj, test_iter, test_dir):
        self.test_dir = test_dir
        self.test_methods = meths
        self.test_obj = obj
        self.iter = test_iter

        self.log=[]
        atexit.register(self.write_log)

    def write_log(self):
        date = datetime.now().strftime('%Y%m%d_%H%M%S')
        flog = self.test_dir + 'test' + date + '.log'
        with open(flog, 'w') as f:
            f.writelines(self.log)

    def test_files(self):

        for f in self.iter:
            self.test_obj.filename = f

            for meth in self.test_methods:
                try:
                    meth(self.test_obj)

                except Exception as err:
                    self.log.append('\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n' +
                                    str(type(err)).rstrip('">').rsplit('.')[-1] + ':' + err.__str__() +
                                    '\n!!!FAILED TO PASS %s!!! for \n%s\n' % (meth, f))
                    # Tests are in a specific order. When failed, subsequent tests fail too.
                    break


class HoboQAQCTests(Tests, object):
    def __init__(self, test_dir):
        hobo_obj = hobo_qaqc.HOBOdata()
        # Test 1. - can it read the header?
        # Test 2. - can it find the column names in the header?
        # Test 3. - can it assign the headers to the right column indices?
        # Test 4. - can it read the numbers and convert them?
        # Test 5. - can it export the full file?
        meths = [self.test_read_header, self.test_get_col, self.test_col_assignment, self.test_units_format,
                 self.test_export2GCE]

        files = [join(test_dir, basename(f)) for f in listdir(test_dir) if
                           f.endswith('.csv')]

        Tests.__init__(self, meths, hobo_obj, files, test_dir)        

        self.log.append('*'*5 + 'TEST hobo_qaqc IMPORT AND EXPORT' + '*'*5)

    def test_read_header(self, qc_obj):
        qc_obj.read_csv_header(qc_obj.filename)
        self.log.append('\n\n' + '----'*10 + '\n' + qc_obj.filename)
        self.log.append('\nHeader:' + str(qc_obj.header))
        self.log.append('\nHeader length:' + str(len(qc_obj.header)))

    def test_get_col(self, qc_obj):
        sep = qc_obj.get_delimiter(qc_obj.header)
        col = qc_obj.get_csv_col(qc_obj.header, sep)
        self.log.append('\nColumns: ' + str(col))

    def test_col_assignment(self, qc_obj):
        qc_obj.load_csv_data(qc_obj.filename)
        self.log.append('\nCol Assignement: .head(1)\n' + str(qc_obj.data.head(1)))
        self.log.append('\nDates: ' + str(qc_obj.data.index.min()) + ' - ' + str(qc_obj.data.index.max()))

    def test_units_format(self, qc_obj):
        qc_obj.format_QAQC_data()
        self.log.append('\nUnits Reformat:\n\tTemp Range: ' + str(qc_obj.data.Temp.describe().ix[['max', 'min']]))

    def test_export2GCE(self, qc_obj):
        f = qc_obj.filename
        dir_end = max(f.rfind('/'), f.rfind('\\'))
        out_path = f[:dir_end] + '/out/processed_' + f[dir_end+1:]
        qc_obj.export_to_GCE_csv(out_path, 'SI', -8)
        self.log.append('\nExport')


class FManagerTests(Tests, object):
    def __init__(self, test_dir, fconfig=None):
        if not fconfig:
            file_obj = file_manager.FileHandling()
        else:
            file_obj = file_manager.FileHandling(config=fconfig)
        # 1. Copy files to working directory (./_data).
        # 2. Attempt to preform QAQC on all .csv files and transfer to ./_processed.
        # 3. Create a .zip file for all .hobo files from each site. Disabled per bitbucket `issue #10`_ .
        # 4. Copy all files with .csv, .log, and unknown extension to final storage.
        # 5. Delete temporary folders in working directory.
        # 6. Write log file.
        # 7. Write log on error?
        meths = [self.test_copy2wkspc, self.test_qaqc_csv, self.test_zip, self.test_copy2final,
                           self.test_del_temp_wkspc, self.test_writelog_on_cmd, self.test_writelog_on_exit]

        test_iter = [1]
        Tests.__init__(self, meths, file_obj, test_iter, test_dir)
        
        self.log = ['*' * 5 + 'TEST file_manager' + '*' * 5 + '\n' + fconfig]

    def test_copy2wkspc(self, qc_obj):
        qc_obj.copy_src_to_wdir()
        srcdir = listdir(qc_obj.src_dir)
        wdir = listdir(qc_obj.data_dir)
        check_copy = srcdir == wdir
        self.log.append('\n' + '-'*10 + '\n')
        self.log.append('\nAll copy correctly?\t' + str(check_copy))

    def test_qaqc_csv(self, qc_obj):
        qc_obj.index_files()
        _, ncsv, nqaqc = qc_obj.qaqc_csv()
        self.log.append('\nQA All:\t' + str(ncsv==nqaqc))
        self.log.append('\nCSV: {ncsv}\nProcessed: {nqaqc}'.format(**locals()))

    def test_zip(self, qc_obj):
        _, nhobo, nzip = qc_obj.zip_hobo_files()
        self.log.append('\nZip {nhobo} .hobo files in {nzip} .zip files'.format(**locals()))

    def test_copy2final(self, qc_obj):
        self.log.append('\nCOPY TO FINAL SERVER')
        if 'map_fname2dir' in qc_obj.__dict__:
           _ = qc_obj.copy_selected_to_site_dir(qc_obj.files['sites'], '_bulk_exp_clean', qc_obj.proc_dir)
        else:
            qc_obj.copy_processed_to_final_dir()

        self.log.append('\nCOPY COMPLETE')

    def test_del_temp_wkspc(self, qc_obj):
        qc_obj.del_temp_folders()
        isempty = not listdir(qc_obj.wdir)
        self.log.append('\nTemp Wkspc Empty:\t{isempty}'.format(**locals()))

    def test_writelog_on_cmd(self, qc_obj):
        qc_obj.write_log()
        self.log.append('\nLog writes on command')

    def test_writelog_on_exit(self, qc_obj):
        try:
            qc_obj.qaqc_csv(time_step='*/-+?><:[]{}||')
        except Exception as ex:
            self.log.append('\nLog writes on error')
            raise ex


if __name__ == '__main__'and __package__ is None:
    # Test valid format clean for GCE
    h = HoboQAQCTests(test_dir='./valid_import/')
    h.test_files()
    # Test that invalid formats raise errors
    i = HoboQAQCTests(test_dir='./raise_import_errors/')
    i.test_files()

    # Test file manager with final subdirs
    k = FManagerTests('./file_manage_tests/', fconfig='./file_manage_tests/file_path_mapdir.config')
    k.test_files()
    k.write_log()
    # Test file manager with single, bulk final dir.
    j = FManagerTests('./file_manage_tests/', fconfig='./file_manage_tests/file_path_bulkdir.config')
    j.test_files()
    j.write_log()
