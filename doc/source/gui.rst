HOBO CSV Date Summary GUI
==========================

``MET_hobo/hobo_date_summary.py`` is a tkinter application for reviewing the date range
covered by a folder of CSV files, deduplicating overlapping sensor downloads, and now for
editing ``file_path.config`` and running the QAQC pipeline directly. Launch it from the
repository root:

.. code-block:: bat

    python MET_hobo\hobo_date_summary.py

Date Summary, Overlap Chart, and Deduplication
------------------------------------------------
Use **Add Folder...** to select one or more source folders, **Scan** to load per-file date
summaries, **Save Summary CSV** to export the results, and **Save Chart PNG** to save the
swim-lane overlap chart. **Deduplicate** writes a deduplicated copy of the scanned files to
the dedupe output directory -- see :doc:`config_file`.

Settings Dialog
----------------
The **Pipeline > Settings...** menu item opens a modal dialog (``settings_dialog.SettingsDialog``)
with one row per ``file_path.config`` key -- the same keys and format
:class:`~file_manager.FileHandling` reads (``FileHandling.load_config``,
``FileHandling._resolve_config_path``); see :doc:`config_file` for what each one does.
Directory fields get a **Browse...** button, and every field has a "(?)" tooltip with a
short description.

**Save** writes ``file_path.config`` to whichever path it would otherwise be resolved from
(explicit path > ``IM_HOBO_CONFIG`` > current directory > repository root), or to the
repository root if none existed yet -- in that case the dialog is first seeded from
``file_path.config.example``. Directories that don't exist yet produce a warning rather than
blocking the save, and output directories (everything except the source directory) can be
created on the spot.

Run and Logging
-----------------
Once Save succeeds, the **Run** button becomes enabled. It runs
``FileHandling(config=...).manage()`` in a background thread (so the dialog's event loop
stays responsive), streaming the pipeline's stdout/stderr into a scrolled log pane via a
thread-safe ``after()``-based redirector. Run is disabled for the duration of the run and
re-enabled on completion or on any exception, which is caught and shown (with its traceback)
in the log pane rather than crashing the dialog.

If ``dedupe_mode`` is set to ``"prompt"``, the console y/N prompt
:meth:`~file_manager.FileHandling._run_dedupe` would otherwise issue is shown instead as a Tk
Yes/No dialog -- ``FileHandling.manage()`` accepts an optional ``confirm_cb`` parameter for
exactly this, so a GUI run never blocks silently on a hidden console prompt.

Every GUI-triggered run's full log is also saved to
``<dir_final_storage>/logs/gui_run_<timestamp>.log`` -- the same ``logs/`` directory
``FileHandling.write_log`` already writes to, just with a distinct filename -- and the saved
path is shown in the log pane and status bar once the run finishes.

Help
-----
The **Help** menu opens this documentation (https://im-hobo.readthedocs.io) in the default
browser, falling back to a local ``doc/build/html/index.html`` or ``README.rst`` if that
fails.

settings_dialog Module
------------------------
.. automodule:: settings_dialog
    :members:
    :undoc-members:
    :show-inheritance:
