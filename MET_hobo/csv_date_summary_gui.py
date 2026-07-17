import csv
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


DATE_FORMATS = (
    '%Y-%m-%d %H:%M:%S',
    '%m/%d/%y %I:%M:%S %p',
    '%m/%d/%Y %I:%M:%S %p',
    '%m/%d/%y %H:%M:%S',
    '%m/%d/%Y %H:%M:%S',
)


def parse_date_value(value):
    """Parse a timestamp string from either processed or raw HOBO CSV files."""
    text = value.strip()
    if not text:
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def find_date_column(row):
    """Return the index of the date column in a CSV header row."""
    normalized = [cell.strip().strip('"').lower() for cell in row]

    for idx, cell in enumerate(normalized):
        if cell == 'date':
            return idx

    for idx, cell in enumerate(normalized):
        if cell == 'date time':
            return idx

    for idx, cell in enumerate(normalized):
        if 'date' in cell and 'time' in cell:
            return idx

    for idx, cell in enumerate(normalized):
        if 'date' in cell:
            return idx

    return None


def summarize_csv_file(path):
    """Read a CSV file and return its first and last timestamp."""
    first_date = None
    last_date = None
    records = 0
    header_found = False

    with path.open('r', newline='', encoding='utf-8-sig', errors='replace') as handle:
        reader = csv.reader(handle)
        date_idx = None

        for row in reader:
            if not row:
                continue

            if date_idx is None:
                date_idx = find_date_column(row)
                if date_idx is not None:
                    header_found = True
                continue

            if date_idx >= len(row):
                continue

            parsed_date = parse_date_value(row[date_idx])
            if parsed_date is None:
                continue

            records += 1
            if first_date is None:
                first_date = parsed_date
            last_date = parsed_date

    if not header_found:
        return {
            'filename': path.name,
            'start_date': '',
            'end_date': '',
            'records': 0,
            'status': 'No Date column found',
        }

    if first_date is None:
        return {
            'filename': path.name,
            'start_date': '',
            'end_date': '',
            'records': 0,
            'status': 'No valid dates found',
        }

    return {
        'filename': path.name,
        'start_date': first_date.strftime('%Y-%m-%d %H:%M:%S'),
        'end_date': last_date.strftime('%Y-%m-%d %H:%M:%S'),
        'records': records,
        'status': 'OK',
    }


def summarize_directory(directory):
    """Return date summaries for all CSV files in a directory."""
    rows = []
    for path in sorted(Path(directory).glob('*.csv')):
        try:
            rows.append(summarize_csv_file(path))
        except Exception as exc:
            rows.append({
                'filename': path.name,
                'start_date': '',
                'end_date': '',
                'records': 0,
                'status': f'Error: {exc}',
            })
    return rows


class CsvDateSummaryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('HOBO CSV Date Summary')
        self.geometry('980x560')
        self.minsize(860, 420)

        self.directory_var = tk.StringVar()
        self.status_var = tk.StringVar(value='Choose a folder of CSV files to summarize.')
        self.rows = []

        self._build_ui()

    def _build_ui(self):
        controls = ttk.Frame(self, padding=12)
        controls.pack(fill='x')

        ttk.Label(controls, text='CSV folder:').pack(side='left')

        entry = ttk.Entry(controls, textvariable=self.directory_var)
        entry.pack(side='left', fill='x', expand=True, padx=(8, 8))

        ttk.Button(controls, text='Browse...', command=self.choose_directory).pack(side='left')
        ttk.Button(controls, text='Scan', command=self.scan_directory).pack(side='left', padx=(8, 0))
        ttk.Button(controls, text='Save Summary CSV', command=self.save_summary).pack(side='left', padx=(8, 0))

        table_frame = ttk.Frame(self, padding=(12, 0, 12, 0))
        table_frame.pack(fill='both', expand=True)

        columns = ('filename', 'start_date', 'end_date', 'records', 'status')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings')
        self.tree.heading('filename', text='Filename')
        self.tree.heading('start_date', text='Start Date')
        self.tree.heading('end_date', text='End Date')
        self.tree.heading('records', text='Records')
        self.tree.heading('status', text='Status')

        self.tree.column('filename', width=280, anchor='w')
        self.tree.column('start_date', width=170, anchor='w')
        self.tree.column('end_date', width=170, anchor='w')
        self.tree.column('records', width=90, anchor='e')
        self.tree.column('status', width=220, anchor='w')

        yscroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        ttk.Label(self, textvariable=self.status_var, padding=12).pack(fill='x')

    def choose_directory(self):
        selected = filedialog.askdirectory(
            title='Select a folder of CSV files',
            initialdir=self.directory_var.get() or str(Path.cwd()),
        )
        if selected:
            self.directory_var.set(selected)

    def scan_directory(self):
        directory = self.directory_var.get().strip()
        if not directory:
            messagebox.showwarning('No folder selected', 'Choose a folder that contains CSV files.')
            return

        folder = Path(directory)
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror('Invalid folder', f'This folder does not exist:\n{folder}')
            return

        self.rows = summarize_directory(folder)
        self._refresh_table()

        csv_count = len(self.rows)
        ok_count = sum(1 for row in self.rows if row['status'] == 'OK')
        self.status_var.set(f'Scanned {csv_count} CSV file(s). {ok_count} file(s) summarized successfully.')

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in self.rows:
            self.tree.insert(
                '',
                'end',
                values=(
                    row['filename'],
                    row['start_date'],
                    row['end_date'],
                    row['records'],
                    row['status'],
                ),
            )

    def save_summary(self):
        if not self.rows:
            messagebox.showinfo('Nothing to save', 'Run a scan before saving the summary.')
            return

        initial_name = f'hobo_date_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        save_path = filedialog.asksaveasfilename(
            title='Save summary CSV',
            defaultextension='.csv',
            initialfile=initial_name,
            filetypes=[('CSV files', '*.csv')],
        )
        if not save_path:
            return

        with Path(save_path).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=['filename', 'start_date', 'end_date', 'records', 'status'],
            )
            writer.writeheader()
            writer.writerows(self.rows)

        self.status_var.set(f'Saved summary to {save_path}')


def main():
    app = CsvDateSummaryApp()
    app.mainloop()


if __name__ == '__main__':
    main()
