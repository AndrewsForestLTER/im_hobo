import hobo
import subprocess
from os import listdir, makedirs
from os.path import isdir
from datetime import datetime
import zipfile as zp

date = datetime.now().strftime('%Y%m%d_%H%M%S')

# load config file as one formatted string
# partial path is a weak point and assumes that pwd is ./MET_hobo/MET_hobo
with open('../file_path.config') as f:
    lines = f.read()

# compile file into pyc (essentially a local .pyc)
pyc = compile(lines, '<string>', 'exec')
# use exec as function for forward compatibility with 3.x (2.x exec can be a statement)
# this process improves speed %12
exec(pyc)


wdir = dir_local_processing

rmot2locl = wdir + '/MET_hobo/bat/mir_hobo_drop.bat'
locl2rmot = wdir + '/MET_hobo/bat/mov_hobo_drop.bat'


def mkdirs_exist_ok(dpath):
    """
    ..To Do::
    In update to >=3.2, mkdirs(exist_ok=True)
    """
    makedirs(dpath) if not isdir(dpath) else False

csv = wdir + '/_csv/'
mkdirs_exist_ok(csv)
processed = wdir + '/_processed/'
mkdirs_exist_ok(processed)

logs = []


# Copy files from server to local machine
proc = subprocess.Popen(rmot2locl, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
logs.extend(proc.communicate())


# Reformat and QAQC all CSV files
start = datetime.now().strftime('%H:%M:%S')
fdir = listdir(csv)
fproc = []
skip = []
for f in fdir:
    if not f.endswith('.csv'):
        skip.append(f + '\n')
        continue
    q = hobo.HOBOdata()
    q.reformat_HOBO_csv(csv+f, processed+f)
    q = None

    fproc.append(f + '\n')

end = datetime.now().strftime('%H:%M:%S')
skip_count = skip.__len__()
fproc_count = fproc.__len__()
fdir_count = fdir.__len__()



# Record log of all file processing
logs.extend('\n\n----------------------------\nStart csv reformat- %s\n----------------------------\n'%start)
logs.extend('---------Read from %s\n'%csv)
logs.extend('---------Ouput to  %s\n'%processed)
logs.extend('--------- %s files total\n'%fdir_count)
logs.extend('--------- %s files processed\n'%fproc_count)
logs.extend('--------- %s files skipped\n'%skip_count)
logs.extend(fproc)
logs.extend('\n\n---------------Skip csv reformat---------------\n')
logs.extend(skip)
time = datetime.now().strftime('%H:%M:%S')
logs.extend('\n\n----------------------------\nEnd csv reformat- %s\n----------------------------\n'%end)
logs.extend('\n\n Start copy TO REMOTE SERVER %s\n***********************************************\n\n'%time)

files = None


# Copy reformated files from local machine back to server
proc = subprocess.Popen(locl2rmot, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
logs.extend(proc.communicate())


'''
+..To do::
+    This is clunky...it is adding files to a zip one at a time. Ideally, it takes the proj+site, and grabs all
+    applicable files at  once and zips...but without dealing with sites that don't have files.
+'''
def get_projname(f):
    name_list = [map_fname2dir[k] for k in map_fname2dir.keys() if k in f.split('_')[0]]
    return name_list[0] if name_list else 'UnknownProject'

for f in skip:
    proj = get_projname(f)
    hobo = f[:-1]
    hobo_path = csv + hobo
    if not proj or not hobo.endswith('.hobo'):
        continue
    site = f.split('_')[0]


    zip_path = dir_final_storage + '/' + proj + '/' + site + '/HOBO/archive/'
    mkdirs_exist_ok(zip_path)

    fzip = zip_path + site + '.zip'
    with zp.ZipFile(fzip, 'a') as zhobo:
        zhobo.write(hobo_path, hobo, compress_type=zp.ZIP_DEFLATED)

log = wdir + '/logs/hobo_qaqc_' + date + '.log'
mkdirs_exist_ok(wdir + '/logs')
with open(log, 'a+') as f:
    f.writelines(logs)
