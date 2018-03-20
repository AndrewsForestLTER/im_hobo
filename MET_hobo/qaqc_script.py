import hobo
import subprocess
from os import listdir
from datetime import datetime

fdir = 'E:/workspace/HOBO_PROCESSING' #'c:/HOBO_DROP/'

date = datetime.now().strftime('%Y%m%d_%H%M%S')
log = fdir + 'hobo_qaqc_' + date + '.log'

rmot2locl = fdir + '/MET_hobo/bat/mir_hobo_drop.bat'
locl2rmot = fdir + '/MET_hobo/bat/mov_hobo_drop.bat'

csv = fdir + '/_csv/'

logs = []


# Copy files from server to local machine
proc = subprocess.Popen(rmot2locl, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
logs.extend(proc.communicate())


# Reformat and QAQC all CSV files
start = datetime.now().strftime('%H:%M:%S')
files = listdir(csv)
skip = []
i = 0
for f in files:
    if not f.endswith('.csv'):
        files.pop(i)
        skip.append(f + '\n')
        continue
    q = hobo.HOBOdata()
    q.reformat_HOBO_csv(csv+f)
    q = None

    files[i] += '\n'
    i += 1
end = datetime.now().strftime('%H:%M:%S')


# Record log of all file processing
logs.extend('\n\n----------------------------\nStart csv reformat- %s\n----------------------------\n'%start)
logs.extend(files)
logs.extend('\n\n---------------Skip csv reformat---------------\n')
logs.extend(skip)
time = datetime.now().strftime('%H:%M:%S')
logs.extend('\n\n----------------------------\nEnd csv reformat- %s\n----------------------------\n'%end)
logs.extend('\n\n Start copy TO REMOTE SERVER %s\n***********************************************\n\n'%time)

files = None


# Copy reformated files from local machine back to server
proc = subprocess.Popen(rmot2locl, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
logs.extend(proc.communicate())

with open(log, 'a+') as f:
    f.writelines(logs)
