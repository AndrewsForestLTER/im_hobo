import pandas as pd
import pytz
from pathlib import Path
from datetime import datetime
from io import StringIO
import re

class HOBOdata:
    def __init__(self, *, logs: list[str]):
        self._logs = logs
        self.header = []
        self.data = pd.DataFrame()
        self.filename = ''
        self.col = []
        self.sep = ''
        self.filtered_lines = []

    def load_csv_data(self, file_path: Path) -> None:
        """Load csv file output by HOBO pendants into a Pandas DataFrame."""
        self.read_csv_header(file_path)
        skip_nrows = len(self.header)
        self.sep = self.get_delimiter(self.header, lineno=-1)
        self.col = self.get_csv_col(self.header, self.sep)
        date_col_i, date_col_n = self.get_timestamp_col(self.col)
        
        # Handle duplicate column names
        col_names = []
        seen = set()
        for col in self.col:
            if col in seen:
                i = 1
                new_col = f"{col}_{i}"
                while new_col in seen:
                    i += 1
                    new_col = f"{col}_{i}"
                col_names.append(new_col)
            else:
                col_names.append(col)
            seen.add(col_names[-1])
        
        # Read the CSV file without parsing dates
        self.data = pd.read_csv(
            StringIO(''.join(self.filtered_lines)),
            delimiter=self.sep,
            skiprows=skip_nrows,
            names=col_names
        )
        if self.data.empty:
            msg = f"Warning: No data rows found in {file_path} after removing lines containing 'Logged'.\n"
            self._logs.append(msg)
            print(msg)
        
        # Parse and validate the datetime column, and set it as the index      
        self.data = self._set_datetime_index(self.data, date_col_n)
        
        # Update the self.col attribute with the new column names
        self.col = col_names

    def _set_datetime_index(self, data: pd.DataFrame, date_col_n: str) -> pd.DataFrame:
        """Set the DataFrame index to the datetime column."""
        input_date_format = '%m/%d/%y %I:%M:%S %p'
        data[date_col_n] = pd.to_datetime(data[date_col_n], format=input_date_format, errors='coerce')
        # Set the index to the date column, but keep the date column in the DataFrame
        data = data.set_index(date_col_n, drop=False)
        # Check parsed dates for validity
        data = self._validate_dates(data)
        return data

    def _validate_dates(self, data: pd.DataFrame) -> pd.DataFrame:
        """Validate the datetime index and drop or warn as needed."""
        # Drop any dates after the current date
        future_dates = data.index > datetime.now()
        if future_dates.any():
            data = data[~future_dates]
            msg = f"Warning: Dropping {future_dates.sum()} rows with invalid future dates in {self.filename}.\n"
            self._logs.append(msg)
            print(msg)

        # Check if any dates failed to parse
        if data.index.isna().any():
            msg = f"Warning: Some dates in {self.filename} could not be parsed.\n"
            self._logs.append(msg)
            print(msg)

        return data

    def read_csv_header(self, file_path: Path):
        """Read the header lines from the beginning of a file."""
        self.filename = str(file_path)
        self.filtered_lines = self.get_filtered_lines(file_path)
        n_lines = self.get_header_nlines(self.filtered_lines)
        if 0 < n_lines < 4:
            self.header = self.filtered_lines[:n_lines]
        else:
            raise ValueError(f'This file does not have a header that matches a recognized HOBOWARE format\nheader n_lines == {n_lines}')

    def get_filtered_lines(self, file_path: Path) -> list:
        """Read file lines, dropping any line containing the text 'Logged'."""
        with file_path.open() as f:
            return [line for line in f if 'logged' not in line.lower()]

    def get_header_nlines(self, lines: list) -> int:
        """Estimate how many header lines exist in a file."""
        for i, line in enumerate(lines):
            if sum(1 for char in line if char.isalpha()) <= 8:
                return i
        # Some HOBO exports can become header-only after removing rows that
        # contain "Logged". In that case we still want to accept the standard
        # two-line header rather than failing the whole batch.
        if len(lines) >= 2 and 'date time' in lines[1].lower():
            return 2
        return 0

    def get_delimiter(self, header: list, lineno: int = -1) -> str:
        """Find the delimiter used in the csv file."""
        header_col = header[lineno]
        for d in (';', '\t', ','):
            if d in header_col:
                return d
        raise KeyError('Cannot find valid delimiter. HOBOware only exports ";" , "\\t" , ","')

    def get_csv_col(self, header: list, sep: str, lineno: int = -1) -> list:
        """Extract column names from csv format."""
        col = self._get_header_line(header, lineno, sep)
        return [c.split(',')[0].split(' ')[0] for c in col]

    @staticmethod
    def _get_header_line(header: list, lineno: int, sep: str) -> list:
        """Break header line into individual parts and strip whitespace and quotes."""
        col_line = header[lineno]
        if sep == ',' and '"' in col_line:
            sep = '","'
        return [s.strip('"') for s in col_line.strip().split(sep)]

    def get_timestamp_col(self, col: list) -> tuple:
        """Get timestamp column(s) information."""
        timestamp_i = [i for i, c in enumerate(col) if 'Date' in c or 'Time' in c]
        if not timestamp_i:
            raise ValueError('No Date or Time column(s) found')
        timestamp_n = [col[i] for i in timestamp_i]
        return ([timestamp_i[0]] if len(timestamp_i) > 1 else timestamp_i,
                f"{timestamp_n[0]}_{timestamp_n[1]}" if len(timestamp_n) > 1 else timestamp_n[0])

    def set_data_GMT_offset(self, hr_offset):
        """Define time zone of DataFrame timestamps in offset from UTC/GMT"""
        min_offset = int(hr_offset * 60)
        gmt_offset = pytz.FixedOffset(min_offset)

        if not isinstance(self.data.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index is not a DatetimeIndex. Cannot perform timezone operations.")

        if self.data.index.tz is None:
            self.data.index = self.data.index.tz_localize(pytz.FixedOffset(int(self.get_csv_GMT_offset(self.header) * 60)))
        
        self.data.index = self.data.index.tz_convert(gmt_offset)
        
        # Update the 'Date' column with the new timezone
        self.data['Date'] = self.data.index

    def format_sync_timestep(self, n_min='5min'):
        """Sync timestamps to a defined measurement interval."""
        if not isinstance(self.data.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index is not a DatetimeIndex. Cannot perform time sync operations.")

        self.data.index = self.data.index.ceil(n_min)
        self.data['Date'] = self.data.index

    def format_QAQC_data(self, units='SI', tz=-8, tstep=None):
        """Reformat the data using basic QAQC for SI or US units and time zone consistency."""
        if units.upper() == 'SI':
            if 'Temp' in self.col:
                self.format_temp(col='Temp', unit='C')
            if 'Intensity' in self.col:
                self.format_intensity(col='Intensity', unit='Lux')
        else:
            raise ValueError(f'{units} is not a supported type of units. See documentation for details')

        self.format_timezone(tz)
        if tstep:
            self.format_sync_timestep(tstep)

    def format_temp(self, col='Temp', unit='C'):
        """Format temperature records to desired units."""
        df = self.data[col].astype('float32')
        if unit == 'C' and not self.is_temp_celsius():
            df = self.temp_F_to_C(df)
        self.data[col] = df

    def format_intensity(self, col='Intensity', unit='Lux'):
        """Format light intensity records in desired units."""
        df = self.data[col]
        if df.dtype == object:
            df = df.str.replace(',', '').astype(float)
        else:
            df = df.astype(float)

        if unit.lower() == 'lux' and not self.is_intensity_lux():
            df = self.intensity_lumft2_to_lux(df)
        self.data[col] = df

    def format_timezone(self, tz=-8):
        """Check that timezone is correct, and if not, adjust the time zone."""
        gmt_num = self.get_csv_GMT_offset(self.header)
        self.set_data_GMT_offset(gmt_num)
        if not self.is_timezone_correct(tz):
            self.set_data_GMT_offset(tz)

    def is_temp_celsius(self):
        """Read units definition from header and return true if units are celsius."""
        units = self.get_csv_temp_unit(self.header)
        return 'C' == units[-1]

    def is_intensity_lux(self):
        """Read units definition from header and return True if units are Lux."""
        units = self.get_csv_intensity_unit(self.header)
        return 'lux' == units[0].lower()

    @staticmethod
    def temp_F_to_C(temp):
        """Convert temperature records from Fahrenheit to Celsius."""
        return (temp - 32) * 5 / 9

    @staticmethod
    def intensity_lumft2_to_lux(intensity):
        """Convert light intensity records from lumen ft-2 into Lux."""
        return intensity * 10.76391

    def get_csv_GMT_offset(self, header, lineno=-1):
        """Get timezone as an offset from Greenwich Mean Time from the header file."""
        reFind_gmt = re.findall('GMT[^"]*', header[lineno])
        if reFind_gmt:
            gmt = reFind_gmt[0].split(':')
        else:
            raise AttributeError('Required attribute: TIME ZONE not found in header!')
        hr = float(gmt[0][3:])
        hr_frac = float(gmt[-1])
        hr += hr_frac / 60
        return hr

    def is_timezone_correct(self, tz):
        """Check the timezone in which data was recorded against the expected timezone."""
        gmt = self.get_csv_GMT_offset(self.header)
        return tz == gmt

    def get_csv_temp_unit(self, header, lineno=-1):
        """Get unit for temperature records."""
        deg = re.findall('\xb0[^ ",]*', header[lineno])
        if deg:
            return deg[-1]
        raise ImportError('No temperature units found in header')

    def get_csv_intensity_unit(self, header, lineno=-1):
        """Get unit for sunlight intensity."""
        return re.findall('(?i)(Lux|lum/ft\xc2\xb2)', header[lineno])

    def export_to_GCE_csv(self, csvname: Path, units: str, tz: float) -> None:
        """Export the HOBO data to a GCE friendly csv file."""
        export_col = ['Date'] + [c for c in ['Temp', 'Intensity'] if c in self.col]
        df = self.data.reset_index(drop=True)  # Reset index to get RecNum
        df.index += 1  # Start RecNum from 1 instead of 0
        df.index.name = 'RecNum'

        t_exp = datetime.now(tz=pytz.utc).strftime('%Y-%m-%d %H:%M')
        tz_orig = self.get_csv_GMT_offset(self.header)
        header_str = (
            f'{self.filename} processed on {t_exp} UTC by {__name__} v{__version__}. '
            f'Orig. record GMT {self.format_gmt_offset(tz_orig)}. '
            f'Output file: GMT {self.format_gmt_offset(tz)}, {units} units, {csvname}\n'
        )

        with csvname.open('w') as f:
            f.write(header_str)
            df.to_csv(f, columns=export_col, date_format='%Y-%m-%d %H:%M:%S', float_format='%g', lineterminator='\n')

    def reformat_HOBO_csv(self, infname: Path, outfname: Path = None, units: str = 'SI', 
                          tz: float = -8, tstep: str = None) -> None:
        """Import a csv file output by HoboWare software, process it, and export to a GCE friendly format."""
        self.load_csv_data(infname)
        self.format_QAQC_data(units=units, tz=tz, tstep=tstep)
        
        if outfname is None:
            outfname = infname.with_name(infname.stem + '_reformat.csv')
        
        self.export_to_GCE_csv(outfname, units, tz)

    @staticmethod
    def format_gmt_offset(hr_offset):
        """Format timezone offset hours as +/-HHMM for export headers."""
        total_minutes = int(round(float(hr_offset) * 60))
        sign = '+' if total_minutes >= 0 else '-'
        total_minutes = abs(total_minutes)
        hours, minutes = divmod(total_minutes, 60)
        return f'{sign}{hours:02d}{minutes:02d}'

# Add these variables at the end of the file
__version__ = '3.0'
__name__ = 'hobo_qaqc'