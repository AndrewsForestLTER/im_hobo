CLS
@echo on

REM --------------------------------GET SYSTEM DATE---------------------------------------
SET TODAY=%date%
ECHO It's %TODAY% today
:: set HOBOMOV=\\server\REFSTANDS\
set DIR=C:\HOBO_DROP\_csv
ECHO Moving data from _csv to destination dir
REM ---------------------------------------------------------------------------------------------


rem move files from stoic to remote server
:: Currently makes directory structure on local drive for testing

set SITE=RS02
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS02_*" /S /mov /XX /log+:logs.log

set SITE=RS04
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS04_*" /S /mov /XX /log+:logs.log

set SITE=RS05
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS05_*" /S /mov /XX /log+:logs.log

set SITE=RS10
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS10_*" /S /mov /XX /log+:logs.log

set SITE=RS12
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS12_*" /S /mov /XX /log+:logs.log

set SITE=RS20
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS20_*" /S /mov /XX /log+:logs.log

set SITE=RS26
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS26_*" /S /mov /XX /log+:logs.log

set SITE=RS38
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS38_*" /S /mov /XX /log+:logs.log

set SITE=RS86
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS86_*" /S /mov /XX /log+:logs.log

set SITE=RS89
If Not Exist "C:\HOBO_DROP\%SITE%" MD "C:\HOBO_DROP\%SITE%"
robocopy %DIR% C:\HOBO_DROP\%SITE% "RS89_*" /S /mov /XX /log+:logs.log
