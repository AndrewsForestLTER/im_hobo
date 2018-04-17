========
MET_hobo
========
This module processes data from hobo data loggers preforming basic QAQC and creating a directory of .hobo
and CSV files formatted for easy import into GCE. Erroneous text and empty columns are removed, timezone is check
and converted to user defined value, measurement units are checked and values converted to user defined units, and
timestep is synced to a standardized interval. All files are removed from the source directory and filed for storage.
All file movement is tracked in log files.

See `module documentation <https://bitbucket.org/hjandrews/met_hobo/downloads/MET_hobo_v0.2.pdf>`_