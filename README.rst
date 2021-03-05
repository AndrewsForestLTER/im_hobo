MET_hobo
========
This module processes data from hobo data loggers preforming basic QAQC and creating a directory of .hobo
and CSV files formatted for easy import into GCE. Erroneous text and empty columns are removed, timezone is checked
and converted to user defined value, measurement units are checked and values converted to user defined units, and
timestep is synced to a standardized interval. All files are removed from the source directory and filed for storage.
All file movement is tracked in log files.

See `module documentation <https://bitbucket.org/hjandrews/im_hobo/downloads/MET_hobo_v0.2.pdf>`_ for use.

Download the module
-------------------
Download the source code
^^^^^^^^^^^^^^^^^^^^^^^^
You can directly download the repository by going to Bitbucket and selecting **Downloads** from the left-side menu.
Download the .zip file for the version you want.

Clone the git repository
^^^^^^^^^^^^^^^^^^^^^^^^
#. Install a current version of git or a GUI with git embeded  [#]_
#. Open a command shell and navigate to a parent directory where you want to store the module
#. Type: ``git clone https://<username>@bitbucket.org/hjandrews/met_hobo.git`` using your username without the angle brackets.

This creates a directory called ``MET_hobo`` that contains the module.

.. [#] : `SourceTree <https://www.sourcetreeapp.com/>`_ or `GitHub Desktop <https://desktop.github.com/>`_

Edit file_path.config
---------------------
You must define the three file directories (source, working, final) and define the timestep of the data being processed.

Run the program
---------------
The module can be imported into Python 2.x and the classes and methods can be accessed. hobo_qaqc can be used to QAQC
data, or file_manager can be used to manage file location

:meth:`file_manager.FileHandling.manage` will run an entire batch process from start to finish. This method will also
be executed when :doc:`file_manager` is called from Python, or from a terminal.

The entire batch process can be initiated from a terminal if Python is in the system path.

.. code-block:: bat

    rem batch execute HOBO QAQC from DOS
    python file_manager.py

If not directly running the module in Python, the configuration of the QA is handled by :doc:`config file <file_path>`.
To manually control time step, units, or time zone, from the command line, **without opening Python**:

.. code-block:: bat

    rem edit QAQC settings of batch from DOS
    .\MET_hobo\MET_hobo>python -c "from file_manager import FileHandling; FileHandling().manage(time_step='20min')"

