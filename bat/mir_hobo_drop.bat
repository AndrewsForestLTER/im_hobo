CLS
@echo on

REM --------------------------------GET SYSTEM DATE---------------------------------------
SET TODAY=%date%
ECHO It's %TODAY% today
::set REMDIR=\\server\HOBO_DROP\bulk_exp
set LOCALDIR=C:\HOBO_DROP\_csv
set REMDIR=E:\workspace\HOBO_PROCESSING\_fake_server\HOBO_DROP
ECHO Moving data from %REMDIR% to %LOCALDRIVE%
REM ---------------------------------------------------------------------------------------------


rem mirror files on remote server to stoic local drive
If Not Exist %LOCALDIR% MD %LOCALDIR%
robocopy %REMDIR%  %LOCALDIR% /e /MIR /TEE /xf *.bat *.tmp
