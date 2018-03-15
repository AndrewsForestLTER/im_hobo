import hobo, cmdLogger
from os import listdir
from datetime import datetime

date = datetime.now().strftime('%Y%m%d_%H%M%S')
fdir = 'c:/HOBO_DROP/'

log = fdir + 'hobo_qaqc_' + date + '.log'
rmot2locl = fdir + '/src/bat/mir_hobo_drop.bat'
locl2rmot = fdir + '/src/bat/mov_hobo_drop.bat'

csv = fdir + '/_csv/'

with open(log, 'a') as f:
    f.write('\n\n Start copy FROM REMOTE SERVER %s\n***********************************************\n\n'%date)



# Copy files from server to local machine
cmd = cmdLogger.CmdLogger()
cmd.setlog(log)
cmd.setCmd(rmot2locl)
cmd.runCmd()


# Reformat and QAQC all CSV files
start = datetime.now().strftime('%H:%M:%S')
files = listdir(csv)
i = 0
for f in files:
    if not f.endswith('.csv'):
        files.pop(i)
        continue
    q = hobo.HOBOdata()
    q.reformat_HOBO_csv(csv+f)
    q = None
    i += 1
end = datetime.now().strftime('%H:%M:%S')


# Record log of all file processing
with open(log, 'a') as f:
    f.write('\n\n----------------------------\nStart csv reformat- %s\n----------------------------\n'%start)
    for l in files:
        f.write(l + '\n')
    time = datetime.now().strftime('%H:%M:%S')
    f.write('\n\n----------------------------\nEnd csv reformat- %s\n----------------------------\n'%end)
    f.write('\n\n Start copy TO REMOTE SERVER %s\n***********************************************\n\n'%time)
    f.flush()
files = None


# Copy reformated files from local machine back to server
cmd.setCmd(locl2rmot)
cmd.runCmd()


