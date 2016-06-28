# coding=utf-8
# date: 3/15/16
# created by: Greg Cohn
__authors__='Greg Cohn'
__version__='0.1'

import pandas as pd
import matplotlib.pyplot as plt
from numpy import shape as shape
from re import findall
import pytz

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

class CampbellData:
    """
    Load and process data from Campbell scientific loggers.

    """

    def __init__(self):
        """
        """
        self.header = []
        self.data = pd.DataFrame()

    def read_txt(self, file_name):
        """
        .. Warning:
            This method is not currently used. 4/22/16

        Read in text file as a list of strings where each string is a row.
        :param file_name: filepath of file to read in
        """
        f = open(file_name)
        filetxt = f.read()
        f.close()

        filelines = filetxt.split('\n')

        self.filetxt = filetxt
        self.filelines = filelines

    def read_header(self, file_name, n_lines=4):
        """
        Read the header lines from the beginning of a file. Reads n_lines, and stores them as headers info.
        :param file_name: str. File path of file to be read.
        :param n_lines: keyword argument. Number of lines in header. i.e. number of lines to read. Default to 4 (toa5)
        """
        f = open(file_name)
        header = [f.next() for l in range(0, n_lines)]
        f.close()

        self.header = header

    def get_cr10_col(self, header):
        """
        Extract column names for CR10 data array
        :param header: array of header lines where each line is a single string.
        :return: array of column names

        .. Note::
            A CR10 data array may contain multiple table id's, each with unique columns. Only one table id is handled
            at a time.
        """
        col = _get_header_line(header, 0)
        return col

    def get_toa5_col(self, header):
        """
        Extract column names from toa5 header format.
        :param header: array of header lines where each line is a single string.
        :return: array of column names.
        """
        col = _get_header_line(header, 1)
        return col

    def get_provisional_col(self, header):
        """
        Extract column names from provisional [1]_ data header format.
        :param header: array of header lines where each line is a single string.
        :return: array of column names.

        .. [1] http://andrewsforest.oregonstate.edu/lter/about/weather/portal/
        """
        col = _get_header_line(header, 2)
        return col

    def get_toa5_units(self, header):
        """
        Extract unit definitions from toa5 header format.
        :param header: array of header lines where each line is a single string.
        :return: array of unit definitions
        """
        units = _get_header_line(header, 2)
        return units

    def get_toa5_collection_method(self, header):
        """
        Extract collection methods from toa5 header format.
        :param header: array of header lines where each line is a single string.
        :return: array of method definitions.
        """
        meth = _get_header_line(header, 3)
        return meth

    def get_toa5_prog(self, header):
        """
        Extract the name of the program that generated the datafile from the toa5 header format.
        :param header: array of header lines where each line is a single string.
        :return: str. Program name.
        """

        return header[0].split(',')[5].strip('"')

    def get_toa5_os(self, header):
        """
        Extract the OS version from the toa5 header format.
        :param header: array of header lines where each line is a single string.
        :return: str. OS number.
        """
        return header[0].split(',')[4].strip('"')


    def get_toa5_progid(self, header):
        """
        Extract program ID from toa5 header
        :param header: array of header lines where each line is a single string
        :return: string containing program ID
        """
        return header[0].split(',')[6]

    def get_toa5_logger(self, header):
        """
        Extract logger type from toa5 header
        :param header: array of header lies where eaqch line is a single string
        :return: string containing program ID
        """
        return header[0].split(',')[2]

    def get_cr10_to_HHMM(self, col):
        """
        Convert time format from CR10 to HHMM.

        :param col: Pandas data Series containing CR10 time values
        :return: array of time as str.
        :return: array of julian day as str

        .. Example::
            CR10 Time   Julian Day
            2345        9
            2400        9
            15          10
            30          10
            45          10
            100         10

            converted to

            2345        9
            0000        10
            0015        10
            0030        10
            0045        10
            0100        10

        """
        four_digit_format = []
        julian_day = []
        for i, r in col.iterrows():
            t = int(r.Time)
            j = int(r.JulianDay)

            len = str(t).__len__()
            HHMM = str(t)
            while len<4:
                HHMM = '0' + HHMM
                len = HHMM.__len__()

            HHMM = '0000' if t == 2400 else HHMM
            j = j+1 if t == 2400 else j
            four_digit_format.append(HHMM)
            julian_day.append(str(j))

        return julian_day, four_digit_format

    def load_csv_data(self, fname, col, skip_nrows=4, time_col=0):
        """
        Load comma delimited data into a Pandas DataFrame indexed by column 0
        :param fname: str. Filepath to datafile
        :param col: array of cloumn names
        :param skip_nrows: number of rows to skip. Start reading from the bottom of the header.
        """
        self.data = pd.read_csv(fname, skiprows=skip_nrows, names=col, parse_dates=True, index_col=time_col)

    def load_toa5_data(self, fname):
        """
        Load toa5 datafile into a Pandas DataFrame
        :param fname: str. Filepath of toa5 data file
        """
        self.read_header(fname)
        col = self.get_toa5_col(self.header)
        self.load_csv_data(fname, col)

    def load_provisional_data(self, fname):
        """
        Load datafile from provisional[1]_ data into a Pandas DataFrame
        :param fname: str. Filepath of provisional datafile

        .. [1] http://andrewsforest.oregonstate.edu/lter/about/weather/portal/
        """
        self.read_header(fname)
        col = self.get_provisional_col(self.header)
        self.load_csv_data(fname, col, skip_nrows=5, time_col=1)

    def load_cr10_array(self, fname, header_file, tbl_id=115):
        """
        Load array from  CR10 data logger.
        :param fname: str. Filepath of cr10 data array.
        :param header_file: str. Filepath to cr10 header file.
        :param tbl_id: int. Identifier of desired table array.

        .. Note::
            self.load_csv_data automatically creates a Pandas DataFrame with table/array ID as the index. This is used
            to take a slice with only the desired table. To access the raw array for multiple slicing, use
            self.load_csv_data

        .. Warning::
            This was designed on Pandas version 0.17.0. Older versions of Pandas may parse the table id as a random date
            This will prevent this method from querying the correct table and will create an invalid date index. To
            upgrade, open a terminal and type:

            pip install --upgrade pandas
        """
        self.read_header(header_file, 1)
        col = self.get_cr10_col(self.header)
        self.load_csv_data(fname, col, skip_nrows=0)

        # slice only the desired table/array ID
        data = self.data.ix[tbl_id]

        # convert Julian Day, Year, and 24 hour time into a time stamp and set as index
        julian_day, time = self.get_cr10_to_HHMM(data[['JulianDay', 'Time']])
        ts = pd.to_datetime(data.Year.astype(str) + ' ' + julian_day + ' ' + time, format='%Y %j %H%M')
        self.data = data.set_index(ts)

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
       export_col = ['RecNum', 'Temp', 'Intensity']
       col = self.get_csv_col(self.header)

       # map desired output to column index
       export_col_index = {'#': 'RecNum'}
       for c in col:
           for ec in export_col:
               if ec in c:
                   export_col_index[c]=ec

       df.rename(columns=export_col_index, inplace=True)
       df.index.rename('Date', inplace=True)

       t_exp = pd.datetime.now(tz=pytz.utc).strftime('%Y-%m-%d %H:%M')
       prog = __name__
       prog_v = __version__
       fname = self.filename
       gmt_orig = self.get_csv_GMT_offset(self.header)

       f = open(csvname, 'w')
       header_str = '%s processed on %s UTC by %s%s. Orig. time GMT %.0f. Output %s\n'%(fname, t_exp, prog, prog_v, gmt_orig, csvname)
       f.write(header_str)
       f.close()

       df.to_csv(csvname, columns=export_col, mode='a')

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
        ts_str = str(tz)
        gmt = self.get_csv_GMT_offset(self.header)
        return True if ts_str == gmt else False

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
        return temp*(5./9.)-32

    def format_temp(self, col='Temp', unit='C'):
        """
        Format temperature records to desired units
        :param col: keyword argurment. Column containing temperature data. Defaults to 'Temp'
        :param unit: keyword argument. str defining desired unit. Default is 'C'
        """
        if unit is 'C':
            self.data = self.temp_F_to_C(col) if not self.is_temp_celsius() else self.data


class MergeData:
    """
    Aggregator class to collect multiple datasets and  merge them together.
    """
    def __init__(self):
        """
        Initialize aggregator class
        """
        self.df = pd.DataFrame()

    def add_toa5_data(self, filename):
        """
        Add a toa5 dataset to the master dataset.
        :param filename: filepath to the toa5 dataset

        Uses self.merge_data to choose the correct method to create an outer 
        join based on DateTimeIndex.
        """
        csi = CampbellData()
        csi.load_toa5_data(filename)

        df = self.merge_data(self.df, csi.data)
        self.df = df

    def add_cr10_data(self, filename, headerfile, tbl_id):
        """
        Add a cr10 data array to the master dataset
        :param filename: filepath to cr10 table array
        :param headerfile: str. Filepath to cr10 header file.
        :param tbl_id: int. Identifier of desired table array.

        Uses self.merge_data to choose the correct method to create an outer 
        join based on DateTimeIndex.
        """
        csi = CampbellData()
        csi.load_cr10_array(filename, headerfile, tbl_id)

        df = self.merge_data(self.df, csi.data)
        self.df = df

    def merge_data(self, data1, data2):
        """
        Merge multiple formats of input datasets.
        :param data1: Pandas DataFrame. The parent or master dataset.
        :param data2: Pandas Data Frame. The child or slave dataset that is 
        merged into data1
        :return: a merged dataset with one set of information for each 
        DateTimeIndex.
        
        Datasets containing different columns names are merged on the 
        DateTimeIndex using an outer join.
        
        Datasets with identical column names are merged using an inner 
        concatenation.
        
        Datasets that contain a subset of the master or parent column names 
        are written to the master DataFrame using timestamp and column indeces. 
        
        .. Note::
            This function will overwrite existing data with newly loaded data.
            The assumption made is that these columns contain empty or NaN v
            alues at these locations. 
        """
        col1 = data1.columns
        col2 = data2.columns
        
        if not self.is_any_columns_common(col1, col2):
            df = data1.join(data2, how='outer')
            
        elif self.is_all_columns_common(col1, col2):
            df = pd.concat([data1, data2], join='outer', ignore_index=False)
            
        elif self.is_all_columns_contained(col1, col2):
            start = data2.index.min()            
            finish = data2.index.max()
            common = self.get_columns_commmon(col1, col2)

            '''
            This is a rare case where 2 or more column structures have been loaded into the data1 (master dataframe),
            and data2 only matches a subset of the column structures present in data1. However data2 fills in a
            timeseries gap, where no valued have been recorded, so data1 cannot be indexed by timestamp
            '''
            if data1.loc[start:finish, common].empty or data1.loc[start:finish, common].shape[0] < data2[start:finish].shape[0]:
                df = pd.concat([data1, data2], join='outer', ignore_index=False).sort_index()
            else:
                data1.loc[start:finish, common] = data2
                df = data1

        elif self.is_any_columns_common(col1, col2):
            # This means that this is NOT a subset of columns, it is NOT a different set of columns
            # this pertains to partially overlapping column names
            df = pd.concat([data1, data2], join='outer', ignore_index=False)

        return df

    def is_any_columns_common(self, columns1, columns2):
        """

        :param columns:
        :return:
        """
        for c in columns1:
            if any(c == columns2):
                return True

        return False
        
    def is_all_columns_common(self, columns1, columns2):
        """
        """
        if not shape(columns1) ==  shape(columns2):
            return False
        elif not all(columns1 == columns2):
            return False
        else:
            return True
    
    def is_all_columns_contained(self, container_columns, contained_columns):
        """

        :param columns:
        :return:
        """
        common = self.get_columns_commmon(container_columns, contained_columns)

        return shape(common)== shape(contained_columns)
        
    def get_columns_commmon(self, columns1, columns2):
        """
        """
        
        return [c for c in columns1 if any(c==columns2)]
        


class ReIndexByTimeCols:
    """
    Data where Max or Min values are logged with a time stamp can be reindexed from multiple timestamp data comlumns.

    In data loggers made by Campbell Scientific, data is stored at a specific time interval, or when a specific
    condition is met (exp: TrigVar). Each log creates a new row with a unique timestamp. However, the value stored
    are a summary of values measured since the last time data was logged. For some summaries, such as max/min, the user
     can specify that the time at which this value occurred is also logged.

     .. Example:
        "TIMESTAMP","RECORD",""SA_TEMP_Max","SA_TEMP_TMx","SA_TEMP_Min","SA_TEMP_TMn"
        "2016-03-14 19:25:00",19,0.936,"2016-03-14 19:25:00",0.907,"2016-03-14 19:21:00"
        "2016-03-14 19:30:00",20,0.936,"2016-03-14 19:29:15",0.917,"2016-03-14 19:26:30"
        "2016-03-14 19:35:00",21,0.936,"2016-03-14 19:34:15",0.917,"2016-03-14 19:30:30"

    This class creates time indexed series out of the data columns and allows mergers of multiple timestamp series
    into a single DataFrame.

    """
    def __init__(self, dataframe):
        """

        :param dataframe: Pandas DataFrames with time stamps in multiple columns.
        """

        self.df = dataframe
        self.df_time_col = pd.DataFrame()
        self.df_merge = pd.DataFrame()

    def get_time_col(self):
        """
        Find columns with timestamps.

        :return: list of column names
        """
        df = self.df
        t = [i for i in df.columns if 'TM' in i]
        return t

    def get_data_col(self, time_col, t_label='_TM'):
        """
        Find a data column that corresponds to a timestamp column.

        .. Example:
            data column name "SA_TEMP_Max"
            timestampe column name "SA_TEMP_TMx"

        :param time_col: Column name in Pandas DataFrame containing timestamp data
        :param t_label: Unique string used to filter timestamp columns
        :return: str. Column name of data column that corresponds to timestamp column
        """
        df = self.df
        data_label = time_col.split(t_label)
        col = [i for i in df.columns if data_label[0] in i and data_label[1] in i and not t_label in i]

        return col[0]

    def col_to_ts(self, time_col, data_col):
        """
        Convert a pair of columns to a Pandas Series with a timestamp index
        :param time_col: Name of column containing timestamps in Pandas DataFrame
        :param data_col: Name of corresponding column containing data in a Pandas DataFrame
        :return: a Pandas timeseries. A Pandas Series with a timestamp index.
        """
        df = self.df

        date = pd.DatetimeIndex(df[time_col])
        if not isinstance(df[data_col].ix[0], float):
            df[data_col] = [float(v) for v in df[data_col]]
        ts = pd.Series(df[data_col].values, index=date)

        return ts

    def dataframe_reindex(self):
        """
        Convert columns containing timestamps into timeseries data and combine into a single DataFrame.

        """
        time_cols = self.get_time_col()
        data = {}
        for tc in time_cols:
            data_col = self.get_data_col(tc)

            ts = self.col_to_ts(tc, data_col)
            data[data_col] = ts

        self.df_time_col = pd.DataFrame(data)

    def get_max_min_keys(self):
        """

        :return:
        """
        columns = self.df_time_col.columns
        keys = {}

        for c in columns:
            k = c.split('_M')[0]
            if k in keys:
                keys[k].append(c)
            else:
                keys[k]=[c]

        return keys

    def merge_max_min(self, keys):
        '''

        :param keys:
        :return:
        '''
        df = self.df_time_col
        data_merge = pd.concat([df[keys[0]], df[keys[-1]]])

        return data_merge

    def dataframe_merge_cols(self):
        """

        :return:
        """
        keys = self.get_max_min_keys()
        data_merge = {}

        for k, v in keys.iteritems():
            new_col = self.merge_max_min(v)

            data_merge[k] = new_col

        self.df_merge = pd.DataFrame(data_merge)

class OffsetTriggerTs:
    """
    This class adds the time offset for the Campbell Scientific tables output using TrigVar.

    CRBasic is the Programable Logic Controler (PLC) language used by second generation data loggers made by Campbell
    Scientific[1]_. The DataTable command can specifiy a TrigVar or Trigger Variable, which is a logical condition
    that dynamically determines when the data table will be recorded.

    .. code-block:: crbasic
        :emphasize-lines: 3

        'CONTROL TALBE- Status of pump program controls
        DataTable(CONT,LogNow=true,-1)
            TableFile("CRD:CENT_234_CONT_",64,-1,0,1,Day,0,0)
            Sample (1,LOGGERID,FP2)
            Sample (1,PROGID,Long)
            Sample (1,PROG_VERS,FP2)
            Sample (1,CON_TIME_OFF,Long)
        EndTable

    The control pumps have a TrigVar that is true when the pump is flagged to turn on or turn off. This capture the
    SA_RUN_TIME or SA_OFF_TIME of the scan that triggers a change in pump status, but does not capture the reset values
     once the pump status has changed. This method adds a time offset to insert the reset values.

    ..[1]https://s.campbellsci.com/documents/us/manuals/cr1000.pdf
    """
    def __init__(self, df):
        """

        :return:
        """
        self.df = df
        self.df_offset = pd.DataFrame()
        self.df_aggr = pd.DataFrame()

    def get_offset_timestamp(self, timestamp, offset=15):
        """

        :param timestamp:
        :param offset:
        :return:
        """
        return timestamp + pd.offsets.DateOffset(seconds=offset)

    def dataframe_shift_ts_index(self, offset=15):
        """

        :param offset:
        :return:
        """
        self.df_offset = self.df.tshift(offset, 's')

    def reset_pump_on(self, pump_on, offset=15):
        """

        :param offset:
        :return:
        """

        self._reset_value(pump_on, 'SA_RUN_TIME', 0)
        self._reset_value(pump_on, 'PUMP_ON', 0)
        self._reset_value(pump_on, 'SA_OFF_TIME', offset)

    def reset_pump_off(self, pump_off, offset=15):
        """

        :param offset:
        :return:
        """
        df_offset = self.df_offset

        self._reset_value(pump_off, 'SA_RUN_TIME', offset)
        self._reset_value(pump_off, 'PUMP_ON', 1)
        self._reset_value(pump_off, 'SA_OFF_TIME', 0)

    def _reset_value(self, loc, col, value):
        """

        :param col:
        :param value:
        :return:
        """
        self.df_offset.loc[loc, col] = value

    def offset_dataframe(self, scan_interval=15):
        """

        :param scan_interval:
        :return:
        """
        self.dataframe_shift_ts_index(scan_interval)
        df_offset = self.df_offset
        pump_off = df_offset['PUMP_ON'] == 0
        pump_on = df_offset['PUMP_ON'] == -1

        self.dataframe_shift_ts_index()
        self.reset_pump_off(pump_off, scan_interval)
        self.reset_pump_on(pump_on, scan_interval)

    def concat_trig_to_offset(self):
        """

        :return:
        """
        self.df_aggr = pd.concat([self.df, self.df_offset]).sort_index()



class PumpOperations:
    """

    """
    def __init__(self, filename):
        """

        :return:
        """
        cont = CampbellData()
        cont.load_toa5_data(filename)

        self.cont = cont.data
        self.cont_offset = pd.DataFrame()

    def check_loggerid(self):
        """

        :return:
        """
        return self._check_constant('LOGGERID')

    def check_prog_vers(self):
        """

        :return:
        """
        return self._check_constant('PROG_VERS')

    def check_progid(self):
        """

        :return:
        """
        return self._check_constant('PROGID')

    def _check_constant(self, col):
        """

        :param col:
        :return:
        """
        desc = self.cont[col].describe()
        min = desc['min']
        max = desc['max']
        mean = desc['mean']
        std = desc['std']

        return min == max == mean and std == 0

    def check_record(self):
        """

        :return:
        """
        desc = self.cont['RECORD'].describe()
        return desc['count']-1 == desc['max'] - desc['min']

    def check_values(self):
        """

        :return:
        """
        for k in ['LOGGERID','PROG_VERS','PROGID']:
            if not self._check_constant(k):
                Warning('%s Is not constant in this file\n'%k)

        if not self.check_record():
            Warning('RECORD number is not monotonically increasing\n')



    def get_num_cycles(self):
        """

        :return:
        """

        return -self.cont.PUMP_ON.sum()

    def get_pump_time(self):
        """

        :return:
        ..note: This should actually be an integrated value
        """
        cont =  self.cont

        run = cont.SA_RUN_TIME.sum()
        off = float(cont.SA_OFF_TIME.sum())


        return run, off, run/off

    def offset_trigger_ts(self):
        """

        :return:
        """
        off = OffsetTriggerTs(self.cont)
        off.offset_dataframe()
        off.concat_trig_to_offset()

        self.cont_offset = off.df_aggr

    def graph_run_time(self):
        """

        :return:
        """
        cont = self.cont

        plt.suptitle('Stand Alone Pump Usage Statistics')
        plt.subplot(2,1,1)
        cont.SA_RUN_TIME[cont.SA_RUN_TIME>0].hist()
        plt.title('RUN_TIME')
        plt.subplot(2,1,2)
        cont.SA_OFF_TIME[cont.SA_OFF_TIME>0].hist(bins=30)
        plt.title('OFF_TIME')

        return plt.gcf()

    def graph_controls(self, cont=None):
        """

        :param cont:
        :return:
        """
        if cont is None:
            cont = self.cont

        plt.suptitle('SA Pump Control Function')
        ax01 = plt.subplot(2,1,1)
        ax012 = cont['PUMP_ON'].plot(kind='area',alpha=0.1,color='k')
        ax01.hold('on')
        ax02 = ax01.twinx()
        ax02.plot(cont.CON_TIME_OFF,color='b',linestyle='--')
        ax01.plot(cont.CON_TIME_ON,color='g',linestyle='--',marker='.')
        ax01.plot(cont.SA_OFF_TIME,color='g',linestyle='-')
        ax02.plot(cont.SA_RUN_TIME,color='b',linestyle='-')
        ax02.legend()
        ax01.legend(loc=2)
        ax02.set_ylabel('Time (s)')

        ax11 = plt.subplot(2,1,2,sharex=ax01)
        ax11 = cont['PUMP_ON'].plot(kind='area',alpha=0.1,color='k')
        ax12 = ax11.twinx()
        # ax11.plot(cont.PUMP_ON, color = 'k')
        ax12.plot(cont.CON_TEMP,color='b',linestyle='--')
        ax12.plot(cont.SA_TEMP)
        ax12.set_ylabel('Temperature (C)')
        ax11.set_ylabel('PUMP_ON')
        ax12.legend()
        ax11.legend(loc=2)
        # somethign about a pair x axis command.

        return plt.gcf(),ax01,ax02,ax11,ax12


class CompareData(MergeData):
    """
    Compare data values. This can compare similar values from the same data stream, or make comparisons across data s
    streams.
    """
    def __init__(self, title):
        """

        :return:
        """
        MergeData.__init__(self)
        self.title = title

    def get_data_lim(self, data, buffer=0.1):
        """
        Evaluates all data in a dataframe, and returns the max and min of all values with a buffer. The default buffer
        is 0.1 (10%)

        :param data: a Pandas DataFrame containing the columns and indexes(rows) to be evaluated
        :param buffer: The method will return the limits plus a buffer. The max value + buffer and the min value -
        buffer. Defaults to 0.1 (10%)
        :return: tuple of min, max values.
        """
        high = max(data.dropna().max())
        low = min(data.dropna().min())
        range = high-low
        high += range * buffer
        low -= range * buffer

        return low, high

    def plot_scatter_matrix(self, columns):
        """

        :param columns:
        :return:
        """
        data = self.df[columns]
        ax = pd.scatter_matrix(data)

        return ax

    def get_diff_sensors(self, columns):
        """

        :param columns:
        :return:
        """
        data = self.df[columns]
        diffs = data.subtract(data[columns[0]],'index')

        return diffs[columns[1:]]

    def plot_compare_sensors(self, columns, units):

        data = self.df[columns]
        diffs = self.get_diff_sensors(columns)


        ax1 = plt.subplot(3, 1, 1)
        x = columns[0]
        y = columns[1:]
        lines1 = plt.plot(data[x], data[y], '.')
        plt.legend(lines1, columns[1:])

        plt.xlabel(x)
        plt.ylabel(units)
        plt.grid('on')

        low, high = self.get_data_lim(data)
        plt.plot([low, high], [low, high], '-k')

        ax2 = plt.subplot(3, 1, 2)
        lines2 = plt.plot(data[x], diffs, '.')

        plt.xlabel(x)
        plt.ylabel(x + ' - Others in ' + units)
        plt.grid('on')
        plt.legend(lines2, columns[1:])

        plt.plot([low, high], [0, 0], '-k')

        ax3 = plt.subplot(3, 1, 3)
        lines3 = plt.plot(diffs.dropna(), '-')

        plt.xlabel('Date')
        plt.ylabel(x + ' - Others in ' + units)
        plt.grid('on')
        plt.legend(lines3, columns[1:])

        plt.plot([diffs.index[0], diffs.index[-1]], [0, 0], '-k')

        plt_title = self.title
        plt.suptitle(plt_title)

        return ax1, ax2, ax3, diffs

if __name__ == "__main__":
    my_path = "c:/workspace/CLIM\\"
    # \\RefStnd\\"
    # "E:\DATA\METDAT\CENMET/"
    #
    # 'E:\workspace\pump_controls\\verrification'
    # #\\TOA5_UPLO_235_CONT_20160229.dat'    #'C:\Users\gcohn\Google Drive\work\pump_controls\\TOA5_UPLO_235_CONT_20160229.dat'
    filename = my_path + "CLIM_2016_040.DAT"
    # "RS02\\2016\\090\\RS02_090_2016_109.dat"
    # "CENT_233_Table105_20160217"
    #
    # '\\update_Mar\\CENT_CONT_Final.dat'
    # uplo = PumpOperations(filename)
    # uplo.cont.CON_TEMP.plot()
    # uplo.cont.SA_TEMP_Avg.plot()
    # plt.title('UPLO Control Table Outputs\n SA temp does not go below CONT_TEMP\n Pump should not be triggered')
    #
    # plt.title('UPLO SA pump run time')
    # uplo.cont.SA_RUN_TIME.hist()
    # plt.ylim([0, 50])
    #
    # uplo.cont[['SA_TEMP_Avg', 'CON_TEMP']].plot()
    # uplo.cont['PUMP_ON'].plot(secondary_y=True,color='r')
    # plt.title('Temperature goes up when the pump is off')
    #
    # ax = uplo.cont[['SA_RUN_TIME', 'SA_OFF_TIME']].plot()
    # x = uplo.cont['SA_TEMP_Avg'].sort_index()
    # ax2 = ax.twinx()
    # ax2.plot(x, color='r')
    # ax.set_ylim(0, 2000)

    # bench = PumpOperations(filename)
    # reindex=IndexByTimeCols(bench.cont)
    # reindex.dataframe_reindex()
    # reindex.dataframe_merge_cols()

    """
    >>> test.SA_OFF_TIME_Max[~np.isnan(test.SA_OFF_TIME_Max)].plot(color='r')
    Out[43]: <matplotlib.axes._subplots.AxesSubplot at 0x19010470>
    >>> test.SA_RUN_TIME_Max[~np.isnan(test.SA_RUN_TIME_Max)].plot(color='b')
    Out[44]: <matplotlib.axes._subplots.AxesSubplot at 0x19010470>
    >>> plt.legend()
    Out[45]: <matplotlib.legend.Legend at 0x146f5470>
    """
    """
    # This is Why MIN MAX doesn't work
    >>> plt.figure()
    Out[82]: <matplotlib.figure.Figure at 0x19d5cef0>
    >>> ax = test.PUMP_ON_Max[~np.isnan(test.PUMP_ON_Max)].plot.area(color=[0.7, 0.7, 0.7])
    >>> ax.plot(test.PUMP_ON_Max[~np.isnan(test.PUMP_ON_Max)], color=[0.1, 0.1, 0.1], marker='x')
    Out[111]: [<matplotlib.lines.Line2D at 0x22436fd0>]
    >>> ax.plot(test.PUMP_ON_Min[~np.isnan(test.PUMP_ON_Min)],color='m',marker='d')
    Out[98]: [<matplotlib.lines.Line2D at 0x1c4245c0>]
    >>> ax.set_ylim(-1.01,0.01)
    Out[106]: (-1.01, 0.01)
    >>> ax2 = ax.twinx()
    >>> ax2.plot(test.SA_OFF_TIME_Max[~np.isnan(test.SA_OFF_TIME_Max)],color='r',marker='o')
    Out[85]: [<matplotlib.lines.Line2D at 0x13886128>]
    >>> ax2.plot(test.SA_RUN_TIME_Max[~np.isnan(test.SA_RUN_TIME_Max)],color='b',marker='o')
    Out[86]: [<matplotlib.lines.Line2D at 0x13898a58>]
    >>> ax2.set_ylim(0,350)
    Out[87]: (0, 350)
    >>> plt.legend()
    Out[88]: <matplotlib.legend.Legend at 0x1387c6a0>
    >>> ax2.legend(loc=2)
    Out[121]: <matplotlib.legend.Legend at 0x229c1438>
    """

    # TEST NEW TRIGGER TABLE CALL
    # trig = PumpOperations(filename)
    # trig.check_values()

    # Test Time Series Offset
    # off = OffsetTriggerTs(trig.cont)
    # off.offset_dataframe()
    # off.concat_trig_to_offset()

    # trig.offset_trigger_ts()
    # trig.graph_controls(trig.cont_offset)

    # TEST AGGREGATOR METHOD
    # meta = "c:/workspace/CLIM\CLIM_115_header.txt"
    # df = CampbellData()
    # df.load_cr10_array(filename, meta)
    #
    # test = MergeData()
    # test.add_toa5_data("c:/workspace/CLIM_113\\2016\CLIM_113_2016_060_Table105.dat")
    # test.add_toa5_data("c:/workspace/CLIM_113\\2016\CLIM_113_2016_089_Table105.dat")
    # test.add_cr10_data("c:/workspace/CLIM\CLIM_2016_040.DAT", meta,115)
    # test.add_cr10_data("c:/workspace/CLIM\CLIM_2016_090.DAT", meta,115)

    # TEST HOBO LOAD
    test = HOBOdata()
    test.load_csv_data('E:\workspace\sensors\\verify\hobo_tests\\557_2013_150.csv')

    x = HOBOdata()
    x.load_csv_data('E:\workspace\sensors/verify\hobo_tests\RS12_2015_180_1___test.csv')
    x.format_timezone(-8)
    x.format_temp()
    x.export_to_GCE_csv('E:\workspace\sensors/verify\hobo_tests\RS12_outtest.csv')


