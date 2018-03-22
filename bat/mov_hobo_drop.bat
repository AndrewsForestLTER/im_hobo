CLS
@echo on

REM --------------------------------GET SYSTEM DATE---------------------------------------
SET TODAY=%date%
ECHO It's %TODAY% today
:: set HOBOMOV=\\server\REFSTANDS\
set HOBOMOV=C:\HOBO_DROP\_csv\test
set DIR=C:\HOBO_DROP\_csv
ECHO Moving data from _csv to destination dir
REM ---------------------------------------------------------------------------------------------


rem move files from stoic to remote server
:: Currently makes directory structure on local drive for testing

REM ---------------------------REFERENCE STANDS------------------------------------------------

set SITE=RS02
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS02_*" /S /mov /XX

set SITE=RS04
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS04_*" /S /mov /XX

set SITE=RS05
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS05_*" /S /mov /XX

set SITE=RS10
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS10_*" /S /mov /XX

set SITE=RS12
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS12_*" /S /mov /XX

set SITE=RS20
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS20_*" /S /mov /XX

set SITE=RS26
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS26_*" /S /mov /XX

set SITE=RS38
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS38_*" /S /mov /XX

set SITE=RS86
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS86_*" /S /mov /XX

set SITE=RS89
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "RS89_*" /S /mov /XX

REM ---------------------------STREAM TEMP------------------------------------------------

set SITE=LOMA
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "%SITE%_*" /S /mov /XX

set SITE=LOMC
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "%SITE%_*" /S /mov /XX

set SITE=LOUP
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "%SITE%_*" /S /mov /XX

set SITE=TSCOLD
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "%SITE%_*" /S /mov /XX

set SITE=TSMACK
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "%SITE%_*" /S /mov /XX

set SITE=TSMCRBR
If Not Exist "%HOBOMOV%\%SITE%" MD "%HOBOMOV%\%SITE%"
robocopy %DIR% %HOBOMOV%\%SITE%\HOBO "%SITE%_*" /S /mov /XX