# coding=utf-8
from re import findall
import pandas as pd
import pytz

# date: 7/06/16
# created by: Greg Cohn
__authors__ = 'Greg Cohn'
__version__ = '1.0'


def _get_header_line(header, lineno, sep):
        """
        Private function. Breaks header line into individual comma delimited parts and strips white space, and double
        quotation marks.

        Example::

            ['"#","Date","Time, GMT-08:00","Temp, \xc2\xb0C (LGR S/N: 920980, SEN S/N: 920980)","Intensity, Lux (LGR S/N:
                920980, SEN S/N: 920980)"\n']

            becomes

            ['#',
             'Date',
             'Time, GMT-08:00',
             'Temp, \xc2\xb0C (LGR S/N: 920980, SEN S/N: 920980)',
             'Intensity, Lux (LGR S/N: 920980, SEN S/N: 920980)']

        :param header: array of header lines where each line is a single string.
        :param lineno: int. Index of line number to be parsed
        :return: list of header components from lineno.
        """
        col_line = header[lineno]
        if sep is ',' and col_line.count('"'):
            sep = '","'

        line = [s.strip('"') for s in col_line.strip().split(sep)]
        return line


class HOBOdata:
    """
    Load and process data from HOBO_ loggers produced by the ONSET company.

    Handles csv files exported from the HoboWare program. The native format for HOBO loggers is a .hobo file. This
    proprietary binary file is not handled here and must be converted to a csv.

    This class syncs timesteps, checks time zones and units (and converts where needed) and strips gratuitous columns.

    To expand included data columns, add to the list `export_col` in :meth:`HOBOdata.export_to_GCE_csv()` and add
    QA methods in :meth:`HOBOdata.format_QAQC_data()`

    .. _HOBO : http://www.onsetcomp.com/hobo-data-loggers
    """
    def __init__(self):
        """
        """
        self.header = []
        self.data = pd.DataFrame()
        self.filename = ''
        self.col = []
        self.sep = ''

    def read_csv_header(self, file_name):
        """
        Read the header lines from the beginning of a file. Reads n_lines, and stores them as headers object.

        :param file_name: str. File path of file to be read.
        """
        self.filename = file_name

        n_lines = self.get_header_nlines(file_name)
        if 4 > n_lines >0:
            with open(file_name) as f:
                header = [f.next() for l in range(0, n_lines)]
        else:
            raise ValueError('This file does not have a header that matches a recognized HOBOWARE format\
            \nheader n_lines == {n_lines}'.format(**locals()))

        self.header = header

    def get_header_nlines(self, file_name):
        """
        Estimate how many header lines exist in a file.

        :param file_name: str containing file path
        :return: int that is index of last header line

        .. Warning::
            This is a simplistic filter that searches for the first row where there are < 8 letters. 8 letters allow for
            12 hour time format (AM/PM) plus 'Logged', while separating number data from text headers

            Complex files with headers that are numerical and special character, or text data will break the method.

        Example::

            'Plot Title: RS12'
            '#','Date Time, GMT-07:00','Temp, °C','Intensity, lum/ft²','Coupler Attached','Stopped','End Of File'
            1,11/17/2014 11:10:00 AM,3.472,16.0,Logged,,

            returns 2
        """
        i = 0
        with open(file_name) as f:
            while True:
                line = f.next()
                find_abc = [char.isalpha() for char in line]
                if find_abc.count(True) > 8:
                    i += 1
                else:
                    break

        return i

    def get_csv_sn(self, header, lineno=-1):
        """
        :param header: array of header lines where each line is a single string.
        :param lineno: keyword argument. index of header array. Function operates on specified index. Default -1
        :return: str containing serial number
        """

        return findall("LGR S/N[^)]*", header[lineno])[0].split(':')[-1]

    def get_csv_GMT_offset(self, header, lineno=-1):
        """
        Get timezone as an offset from Greenwhich Mean Time from the header file

        :param lineno: keyword argument. index of header array. Function operates on specified index. Default -1
        :param header: array of header lines where each line is a single string.
        :return: string of timezone offset from GMT

        Example::

            String for PST  '-08:00'
        """
        reFind_gmt = findall('GMT[^"]*', header[lineno])

        if reFind_gmt:
            gmt = reFind_gmt[0].split(':')
        elif not reFind_gmt:
            raise AttributeError('Required attribute: TIME ZONE not found in header!\nTo export time zone from '\
                'HOBOware:\nGo to Preferences>>General>>Export Settings:\nDE-SELECT option, "No quotes or commas in' \
                'headings, properties in parentheses"\n')

        hr = float(gmt[0][3:])
        hr_frac = float(gmt[-1])
        hr += hr_frac
        return hr

    def get_csv_temp_unit(self, header, lineno=-1):
        """
        Get unit for temperature records

        :param header: array of header lines where each line is a single string.
        :param lineno: keyword argument. index of header array. Function operates on specified index. Default -1
        :return: str with single letter defining units for temperature.
        """
        deg = findall('\xb0[^ ",]*', header[lineno])
        return deg[-1]

    def get_csv_intensity_unit(self, header, lineno=-1):
        """
        Get unit for sunlight intensity

        :param header: array of header lines where each line is a single string
        :param lineno: keyword argument. index of header array. Function operates on specified index. Default -1
        :return: str defining units for sunlight intensity
        """
        intensity = findall('(?i)(Lux|lum/ft\xc2\xb2)', header[lineno])
        return intensity

    def get_csv_col(self, header, sep, lineno=-1):
        """
        Extract column names from csv format.

        From multiple header lines, this extracts a single line, and strips extra info, leaving only column names. File
        delimiter is used to split header into columns, and ',' is used to split info within a column.

        Example::

            Singles string header:
            ['"#","Date","Time, GMT-08:00","Temp, \xc2\xb0C (LGR S/N: 920980, SEN S/N: 920980)","Intensity, Lux (LGR S/N:
            920980, SEN S/N: 920980)"\\n']

            becomes a list of column strings:

            ['#', 'Date', 'Time', 'Temp', 'Intensity']

        :param header: array of header lines where each line is a single string.
        :param lineno: keyword argument. index of header array. Function operates on specified index. Default -1
        :return: array of column names.
        """
        col = _get_header_line(header, lineno, sep)
        col_edit = []
        for c in col:
            #str_wo_utf_head = c.decode("utf-8-sig").encode("utf-8")
            first_of_parts =c.split(',')[0].split(' ')[0]
            col_edit.append(first_of_parts)

        return col_edit

    def get_timestamp_col(self, col):
        """
        Time stamps can be exported by HOBO into either 1 or 2 columns

        :param col: an array of column names
        :return: list of index locations
        :return: list of column name(s) that make the timestamp
        """
        i = 0
        timestamp_i = []
        timestamp_n = []
        for c in col:
            if 'Date' in c or 'Time' in c:
                timestamp_i.append(i)
                timestamp_n.append(c)
            i += 1

        if timestamp_i.__len__() > 1:
            timestamp_col = timestamp_n[0] + '_' + timestamp_n[1]
            timestamp_i = [timestamp_i]
        elif not timestamp_i or not timestamp_n:
            raise ValueError('No Date or Time column(s) found')
        else:
             timestamp_col = timestamp_n[0]

        return timestamp_i, timestamp_col

    def get_delimiter(self, header, lineno=-1):
        """
        Find the delimiter used in the csv file.

        AS of 3/9/21, the only possible delimiters when exporting from HOBOware are \t, ; and , . This method tests for
        which one is used, and returns the answer.

        :param header: array of header lines where each line is a single string.
        :param lineno: keyword argument. index of header array. Function operates on specified index. Default -1
        :return: str containing delimiter
        """
        header_col = header[lineno]
        possible_delimiters = [';', '\t', ',']
        for d in possible_delimiters:
            if d in header_col:
                return d
        raise KeyError('Cannot find valid delimiter.\nHOBOware only exports ";" , "\\t" , ","')

    def load_csv_data(self, fname):
        """
        Load csv file output by HOBO pendants into a Pandas DataFrame.

        :param fname: str. Filepath of csv data file
        """

        self.read_csv_header(fname)
        skip_nrows = self.header.__len__()
        self.sep = self.get_delimiter(self.header, lineno=-1)
        col = self.get_csv_col(self.header, self.sep)
        date_col_i, date_col_n = self.get_timestamp_col(col)
        self.data = pd.read_csv(fname, delimiter=self.sep, parse_dates=date_col_i, skiprows=skip_nrows, names=col,
                                index_col=date_col_n)
        self.col = col

    def export_to_GCE_csv(self, csvname, units, tz):
        """
        Export the HOBO data to a GCE_ friendly csv file

        :param csvname: str. Filepath to output csv file
        :param units: str. Units of output data. Example: 'SI'.
        :param tz: float. GMT time zone of output data series. Example: -8.

        .. _GCE : https://gce-lter.marsci.uga.edu/public/im/tools/data_toolbox.htm
        """
        col = self.col
        '''
        export column is important for oddball HOBO settings that split timestamps btwn columns and add erroneous columns
        such as:
        .. Example::
            '#',
             'Date',
             'Time',
             'Temp',
             'Intensity',
             'Coupler Attached (LGR S/N: 10335619)',
             'Stopped (LGR S/N: 10335619)',
             'End Of File (LGR S/N: 10335619)'
        '''
        export_col = ['Date']
        for c in ['Temp', 'Intensity']:
            export_col.append(c) if c in col else None
        data = self.data
        df = data.dropna(subset=export_col[1:])
        data = None

        df.loc[:, 'Date'] = df.index
        if '#' in df.columns:
            # record number present
            df.set_index(keys='#', drop=True, inplace=True)
        else:
            # No record number present (reset_index() is 0 based, but same speed)
            df.index = pd.RangeIndex(start=1, stop=len(df)+1, step=1)

        df.index.rename('RecNum', inplace=True)

        t_exp = pd.datetime.now(tz=pytz.utc).strftime('%Y-%m-%d %H:%M')
        prog = __name__
        prog_v = __version__
        fname = self.filename
        tz_orig = self.get_csv_GMT_offset(self.header)

        header_str = '{fname} processed on {t_exp} UTC by {prog} v{prog_v}. Orig. record GMT {tz_orig}. Output file: \
        GMT {tz}, {units} units, {csvname}\n'.format(**locals())

        with open(csvname, 'w') as f:
            f.write(header_str)

        with open(csvname, mode='a') as f:
            df.to_csv(f, columns=export_col, mode='a', date_format='%Y-%m-%d %H:%M', float_format='%g',
                      line_terminator='\n')

    def set_data_GMT_offset(self, hr_offset):
        """
        Define time zone of DataFrame timestamps in offset from UTC/GMT

        :param hr_offset: floating point of time zone in hours difference from Greenwhich Mean Time
        """
        ts = self.data
        min_offset = hr_offset * 60
        gmt_offset = pytz.FixedOffset(min_offset)

        if ts.index.tz is None:
            self.data = ts.tz_localize(gmt_offset)
        else:
            self.data = ts.tz_convert(gmt_offset)

    def is_timezone_correct(self, tz):
        """
        Check the timezone in which data was recorded against the expected timezone

        :param tz: a timezone as number of hours offset from Greenwhich Mean Time
        :return: Boolean
        """
        #ts_str = str(tz)
        gmt = self.get_csv_GMT_offset(self.header)
        return True if tz == gmt else False

    def format_timezone(self, tz=-8):
        """
        Check that timezone is correct, and if not, adjust the time zone.

        :param tz: a timezone as number of hours offset from Greenwhich Mean Time
        """
        gmt_num = self.get_csv_GMT_offset(self.header)
        self.set_data_GMT_offset(gmt_num)
        if not self.is_timezone_correct(tz):
            self.set_data_GMT_offset(tz)

    def format_sync_timestep(self, n_min='5min'):
        """
        Sync timestamps to a defined measurement interval. Timestamps are increased to the next defined interval.

        :param n_min: str. keyword argument. Interval to round time stamps to. Default '5min'.

        .. Note::
            This uses the function ceil to round up to the next interval. The interval provided must match a known type
            and contain both a number and a letter such as '1D' to round up to the next whole day.

            See documentation for valid types [#]_

        .. Warning::
            This will change the index and timestamp of every record.

        .. [#] : https://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases
        """

        df = self.data.index
        sync = df.ceil(n_min)
        self.data.index = sync

    def is_temp_celsius(self):
        """
        Read units definition from header and return true if units are celsius

        :return: Boolean. True if temperature is recorded in celsius.
        """
        units = self.get_csv_temp_unit(self.header)
        return 'C' == units[-1]

    def temp_F_to_C(self, temp):
        """
        Convert temperature records from Fahrenheit

        :param temp: a temperature value or list of temperature values in degrees fahrenheit.
        :return: a temperature value or list of temperature values in degrees celsius
        """
        return (temp-32)*5./9.

    def format_temp(self, col='Temp', unit='C'):
        """
        Format temperature records to desired units

        :param col: keyword argurment. str. Name of column containing temperature data. Defaults to 'Temp'
        :param unit: keyword argument. str defining desired unit. Default is 'C'
        """

        df = self.data[col].astype('float32')

        if unit == 'C':
            df = df if self.is_temp_celsius() else self.temp_F_to_C(df)

        self.data[col] = df

    def is_intensity_lux(self):
        """
        Read units definition from header and return True if units are Lux

        :return: Boolean. True if light intensity is recorded in Lux
        """
        units = self.get_csv_intensity_unit(self.header)
        return 'lux' == units[0].lower()

    def intensity_lumft2_to_lux(self, intensity):
        """
        Convert light intensity records from lumen ft-2 into Lux

        :param intensity: an intensity value or list of intensity values in lumen ft-2
        :return: an intensity or list of intensity values in Lux
        """

        return intensity*10.76391

    def format_intensity(self, col='Intensity', unit='Lux'):
        """
        Format light intensity records in desired units

        :param col: keyword argument. str. Name of column containing light intensity data. Defaults to 'Intensity'.
        :param unit: keyword argument. str defining desired units. Default is 'Lux' (SI)
        """
        df = self.data[col]

        if not df._is_numeric_mixed_type:
            # if commas are used in the thousands place, remove, before converting to float
            df = df.str.replace(',', '')
        df = df.astype('float32')

        if unit.lower() == 'lux':
            df = df if self.is_intensity_lux() else self.intensity_lumft2_to_lux(df)

        self.data[col] = df

    def format_QAQC_data(self, units='SI', tz=-8, tstep='5min'):
        """
        Reformat the data using basic QAQC for SI or US units and time zone consistency regardless of daylight savings.

        :param units: str. keyword argument. The desired system of units. Default is 'SI'.
        :param tz: flt. keyword argument. The desired time zone as an offset from Greenwich Mean Time. Default is -8 (PST)
        :param tstep: keyword argument. Interval to round time stamps to. Default '5min'.

        .. Note::
            tstep is input to the function :meth:`HOBOdata.format_sync_timestep()`. Valid types are listed there.
        """
        col = self.col
        if units.upper() == 'SI':
            self.format_temp(col='Temp', unit='C') if 'Temp' in col else None
            self.format_intensity(col='Intensity', unit='Lux') if 'Intensity' in col else None
        else:
            raise ValueError('%s is not a supported type of units. See documentation for details\n'%units)

        self.format_timezone(tz)

        # sync time to correct time intervals
        self.format_sync_timestep(tstep)

    def reformat_HOBO_csv(self, infname, outfname=None, units='SI', tz=-8, tstep='5min'):
        """
        Imports a csv file output by HoboWare software and checks for:

        * units
        * timezone
        * time sync (09:07 vs 09:05)

        File is converted to specified settings and exported to a GCE_ friendly format.

        :param infname: str. Filename to read
        :param outfname: str. Filename to ouput. Defaults to same as infname
        :param units: str. System of units desired. Defaults to SI
        :param tz: int or flt. Timezone as offset from GMT
        :param tstep: str. Time interval to sync to. Default is '5min'. See :meth:`HOBOdata.format_sync_timestep()`
         or [#]_ for valid formats.

        .. _GCE : https://gce-lter.marsci.uga.edu/public/im/tools/data_toolbox.htm
        .. [#] : https://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases
        """
        self.load_csv_data(infname)
        self.format_QAQC_data(units=units, tz=tz, tstep=tstep)

        if outfname is None:
            csvname = infname.replace('.csv', '_reformat.csv')
        else:
            csvname = outfname

        self.export_to_GCE_csv(csvname, units, tz)


if __name__ == "__main__":
    # TEST HOBO LOAD
    test = HOBOdata()
    test.load_csv_data('E:\workspace\sensors\\verify\hobo_tests\\557_2013_150.csv')

    x = HOBOdata()
    x.load_csv_data('E:\workspace\sensors/verify\hobo_tests\RS12_2015_180_1___test.csv')
    x.format_timezone(-8)
    x.format_temp()
    x.export_to_GCE_csv('E:\workspace\sensors/verify\hobo_tests\\New_outtest.csv')
