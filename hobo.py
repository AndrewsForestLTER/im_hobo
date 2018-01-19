# coding=utf-8
from re import findall
import pandas as pd
import pytz

# date: 7/06/16
# created by: Greg Cohn
__authors__ = 'Greg Cohn'
__version__ = '0.1'


def _get_header_line(header, lineno):
        """
        Private function. Breaks header line into individual comma delimited parts and strips white space, and double
        quotation marks.
        :param header: array of header lines where each line is a single string.
        :param lineno: int. Index of line number to be parsed
        :return: array of header components from lineno.
        """
        line = [s.strip('"') for s in header[lineno].strip().split('","')]
        return line


class HOBOdata:
    """
    Load and process data from HOBO_ loggers produced by the ONSET company.

    .. _HOBO : http://www.onsetcomp.com/hobo-data-loggers
    """
    def __init__(self):
        """
        """
        self.header = []
        self.data = pd.DataFrame()
        self.filename = ''

    def read_csv_header(self, file_name):
        """
        Read the header lines from the beginning of a file. Reads n_lines, and stores them as headers object.
        :param file_name: str. File path of file to be read.
        :param n_lines: keyword argument. Number of lines in header. i.e. number of lines to read. Default to 2
        """
        self.filename = file_name

        n_lines = self.get_header_nlines(file_name)
        f = open(file_name)
        header = [f.next() for l in range(0, n_lines)]
        f.close()

        self.header = header

    def get_header_nlines(self, file_name):
        """
        Estimate how many header lines exist in a file
        :param file_name:
        :return:

        .. Warning::
            This is a simplistic filter that searches for the first row where there are no quotes and returns line_num
            - 1 on a 1 based index.
             Complex files with quotes around data fields, or no quotes in header lines will not be caught.

        .. Example::
            'Plot Title: RS12'
            '#','Date Time, GMT-07:00','Temp, °C','Intensity, lum/ft²','Coupler Attached','Stopped','End Of File'
            1,11/17/2014 11:10:00 AM,3.472,16.0,,,

            returns 2
        """
        i = 0
        f = open(file_name)
        while True:
            l = f.next().count('"')
            if l is 0:
                break
            else:
                i += 1

        f.close()
        return i

    def get_csv_sn(self, header, lineno=-1):
        """
        :param header: array of header lines where each line is a single string.
        :param lineno: keyword argument. index of header array. Function operates on specified index. Default -1
        :return:
        """

        return findall("LGR S/N[^)]*", header[lineno])[0].split(':')[-1]

    def get_csv_GMT_offset(self, header, lineno=-1):
        """
        Get timezone as an offset from Greenwhich Mean Time from the header file
        :param lineno: keyword argument. index of header array. Function operates on specified index. Default -1
        :param header: array of header lines where each line is a single string.
        :return: string of timezone offset from GMT
        ..Example PST
             '-08:00'
        """
        gmt = findall('GMT[^"]*', header[lineno])[0].split(':')
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

    def get_csv_col(self, header, lineno=-1):
        """
        Extract column names from csv format
        :param header: array of header lines where each line is a single string.
        :param lineno: keyword argument. index of header array. Function operates on specified index. Default -1
        :return: array of column names.
        """
        col = _get_header_line(header, lineno)
        col_edit = []
        for c in col:
            col_edit.append(c.split(',')[0])

        return col_edit

    def get_timestamp_col(self, col):
        """
        Time stamps can be exported by HOBO into either 1 or 2 columns
        :param col: an array of column names
        :return: array of index locations
        :return: array of column name(s) that make the timestamp
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
        else:
             timestamp_col = timestamp_n[0]

        return timestamp_i, timestamp_col

    def load_csv_data(self, fname):
        """
        Load csv file output by HOBO pendants into a Pandas DataFrame.
        :param fname: str. Filepath of csv data file
        :param skip_nrows: number of rows to skip. Start reading from the bottom of the header.
        :param col_line: a 0 based index identifying which line contains the column names.
        """

        self.read_csv_header(fname)
        skip_nrows = self.header.__len__()
        col = self.get_csv_col(self.header)
        date_col_i, date_col_n = self.get_timestamp_col(col)
        self.data = pd.read_csv(fname, parse_dates=date_col_i, skiprows=skip_nrows, names=col, index_col=date_col_n)

    def export_to_GCE_csv(self, csvname):
       """
       Export the HOBO data to a GCE friendly csv file
       :param csvname: str. Filepath to output csv file
       :param col_line: a 0 based index identifying which line contains the column names.
       """
       df = self.data
       export_col = ['Date', 'Temp', 'Intensity']
       col = self.get_csv_col(self.header)

       """
       # map desired output to column index
       export_col_index = {'#': 'RecNum'}
       for c in col:
           for ec in export_col:
               if ec in c:
                   export_col_index[c]=ec

        df.rename(columns=export_col_index, inplace=True)
       """

       df['Date'] = df.index
       df.set_index(keys='#', drop=True, inplace=True)
       df.index.rename('RecNum', inplace=True)

       t_exp = pd.datetime.now(tz=pytz.utc).strftime('%Y-%m-%d %H:%M')
       prog = __name__
       prog_v = __version__
       fname = self.filename
       gmt_orig = self.get_csv_GMT_offset(self.header)

       f = open(csvname, 'w')
       header_str = '%s processed on %s UTC by %s v%s. Orig. record GMT %.0f. Output file %s\n'%(fname, t_exp, prog, prog_v, gmt_orig, csvname)
       f.write(header_str)
       f.close()

       df.to_csv(csvname, columns=export_col, mode='a', date_format='%m-%d-%Y %H:%M')

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
        :return: Logical variable
        """
        #ts_str = str(tz)
        gmt = self.get_csv_GMT_offset(self.header)
        return True if tz == gmt else False

    def format_timezone(self, tz=-8):
        """
        Check that timezone is correct, and if not, adjust the time zone.
        :param tz:a timezone as number of hours offset from Greenwhich Mean Time
        :return:
        """
        gmt_num = self.get_csv_GMT_offset(self.header)
        self.set_data_GMT_offset(gmt_num)
        if not self.is_timezone_correct(tz):
            self.set_data_GMT_offset(tz)

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
        :param col: keyword argurment. Column containing temperature data. Defaults to 'Temp'
        :param unit: keyword argument. str defining desired unit. Default is 'C'
        """

        df = self.data

        if unit == 'C':
            df[col] = self.temp_F_to_C(df[col]) if not self.is_temp_celsius() else df[col]

        self.data = df

    def is_intensity_lux(self):
        """
        Read units definition from header and return True if units are Lux
        :return: Boolean. True if light intensity is recorded in Lux
        """
        units = self.get_csv_intensity_unit(self.header)
        return 'lux' == units[0].lower()

    def intensity_lumft2_to_lux(self, intensity):
        '''
        Convert light intensity records from lumen ft-2 into Lux
        :param intensity: an intensity value or list of intensity values in lumen ft-2
        :return: an intensity or list of intensity values in Lux
        '''

        return intensity*10.76391

    def format_intensity(self, col='Intensity', unit='Lux'):
        '''
        Format light intensity records in desired units
        :param col: keyword argument. Column containing light intensity data. Defaults to Intensity
        :param unit: keyword argument. str defining desired units. Default is 'Lux' (SI)
        :return:
        '''

        df = self.data
        if unit.lower() == 'lux':
            df[col] = self.intensity_lumft2_to_lux(df[col]) if not self.is_intensity_lux() else df[col]

        self.data = df

    def format_QAQC_data(self, units='SI', tz=-8, tstep=5):
        '''
        Reformat the data using basic QAQC for SI or US units and time zone consistency regardless of daylight savings.
        :param units: str. keyword argument. The desired system of units. Default is 'SI'.
        :param tz: flt. keyword argument. The desired time zone as an offset from Greenwich Mean Time. Default is -8 (PST)
        :param intvl: int. keyword argument. The desired time step for the data in minutes. Default is 5
        '''
        if units.upper() == 'SI':
            self.format_temp(col='Temp', unit='C')
            self.format_intensity(col='Intensity', unit='Lux')

        self.format_timezone(tz)

        # sync time to correct time intervals
        df = self.data
        sync = df.resample(str(tstep)+'T', closed='left').mean()
        self.data = sync

    def reformat_HOBO_csv(self, fname, units='SI', tz=-8):
        '''

        :return:
        '''
        self.load_csv_data(fname)
        self.format_QAQC_data(units=units, tz=tz)

        csvname = fname.replace('.csv','_reformat.csv')
        self.export_to_GCE_csv(csvname)


if __name__ == "__main__":
    # TEST HOBO LOAD
    test = HOBOdata()
    test.load_csv_data('E:\workspace\sensors\\verify\hobo_tests\\557_2013_150.csv')

    x = HOBOdata()
    x.load_csv_data('E:\workspace\sensors/verify\hobo_tests\RS12_2015_180_1___test.csv')
    x.format_timezone(-8)
    x.format_temp()
    x.export_to_GCE_csv('E:\workspace\sensors/verify\hobo_tests\New_outtest.csv')
