Config File
===========

Assigning directories
---------------------
``MET_hobo/file_path.config``  must be **edited by each user.** It defines 3 directories:

* ``dir_source_files`` - QAQC will be attempted on every csv file in this directory. The module contains options for wiping original files from this directory. This can be a server path.
* ``dir_local_processing`` -  A temporary working directory. This directory is populated during processing, and wipes all temporary files and folders when processing is complete. It is recommended that this directory be local to the machine running the module.
* ``dir_final_storage`` - A directory where processed files, and any non-csv files, will be ultimately saved

.. Warning::
    The file is directly executed by Python, and must follow standard Python syntax, or it will generate an error.

Other Config Parameters
------------------------
time_step
^^^^^^^^^
Each file will be synchronized to whole values of this interval. Must be a `Pandas timeseries`_ string.

map_fname2dir
^^^^^^^^^^^^^
Optional parameter.
This Python dictionary_ is used to map to multiple final storage directories. The key (left side of : ) is an identifying string of
characters that will be in every file name. The values (right side of : ) are a project name associated with those
files. This will then place all identified files into 
``<dir_final_storage>/<value, projname right of "_">/<key, filename left of "_">/<filename>``

Example::
	
	```
	map_fname2dir = {'RS':'REFSTAND'} 	
	file = 'RS12_20160901.csv'	
	# creates 	
	<dir_final_storage>/REFSTAND/RS12/RS12_20160901.csv
	```

.. _`Pandas timeseries`: https://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases
.. _dictionary: https://docs.python.org/2/tutorial/datastructures.html#dictionaries

