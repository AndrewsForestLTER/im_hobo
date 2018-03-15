CLS
@echo on

REM --------------------------------GET SYSTEM DATE---------------------------------------
SET TODAY=%date%
ECHO It's %TODAY% today
set EMPTY=C:\HOBO_DROP\_empty
set PURGE=C:\HOBO_DROP\_csv
ECHO Wipe files from _csv directory
REM ---------------------------------------------------------------------------------------------

If Not Exist %EMPTY% MD %EMPTY%
robocopy %EMPTY% %PURGE% /purge /log+:logs.log
