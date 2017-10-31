# coding=utf-8
import pandas as pd
from numpy import shape
from csi import CampbellData
from hobo import HOBOdata

# date: 7/06/16
# created by: Greg Cohn
__authors__ = 'Greg Cohn'
__version__ = '0.1'

class Data_File:
    """
    generic file handling methods
    """

    def __init__(self):
        """

        """
        self.header = []
        self.data = pd.DataFrame()

    def _get_header_line(self, header, lineno, splitstr='","'):
        """
        Private function. Breaks header line into individual comma delimited parts and strips white space, and double
        quotation marks.
        :param header: array of header lines where each line is a single string.
        :param lineno: int. Index of line number to be parsed
        :param splitstr: str identifying the delimeter for the header line
        :return: array of header components from lineno.
        """
        line = [s.strip('"') for s in header[lineno].strip().split(splitstr)]
        return line

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

    def load_csv_data(self, fname, col, skip_nrows=4, time_col=[0]):
        """
        Load comma delimited data into a Pandas DataFrame indexed by column 0
        :param fname: str. Filepath to datafile
        :param col: array of cloumn names
        :param skip_nrows: number of rows to skip. Start reading from the bottom of the header.
        """
        self.data = pd.read_csv(fname, skiprows=skip_nrows, names=col, parse_dates=True, index_col=time_col)

class HJ_Data(Data_File):
    """
    Load both provisional [1]_ and final [2]_ data processed  for quality assurance by the HJ Andrews Information
    Management group.

    .. Note::
        Data initially undergoes a combination of auotmated and manually QAQC using the GCE_ program. This data is
        considered provisional [1]_. It then undergoes a more thorough processing for final [2]_ storage in and SQL
        database.

        .. _GCE : https://gce-lter.marsci.uga.edu/public/im/tools/data_toolbox.htm

    .. _[1] : http://andrewsforest.oregonstate.edu/lter/about/weather/portal/
    .. _[2] : http://andrewsforest.oregonstate.edu/lter/about/weather/hja.cfm?topnav=16
    """
    def __init__(self):
        """

        """
        Data_File.__init__(self)

    def get_provisional_col(self, header):
        """
        Extract column names from provisional [1]_ data header format.
        :param header: array of header lines where each line is a single string.
        :return: array of column names.

        .. _[1] http://andrewsforest.oregonstate.edu/lter/about/weather/portal/
        """
        col = self._get_header_line(header, 2)
        return col

    def get_ms001_col(self, header):
        """
        Extract column names from ms001 [2]_ data header format.
        :param header: header: array of header lines where each line is a single string.
        :return: array of column names

        .. _[2] : http://andrewsforest.oregonstate.edu/lter/about/weather/hja.cfm?topnav=16
        """
        col = self._get_header_line(header, lineno=0, splitstr=",")
        return col

    def get_date_time_cols(self, col_names):
        """
        Identify the column number or numbers containing date and time information
        :param col_names: list of column names extracted from header
        :return: list of column indexes that contain date and time information
        """
        return [c for c in range(0, col_names.__len__(), 1) if 'date' in col_names[c].lower() or 'time' in col_names[c].lower() and not 'max'in col_names[c].lower() and not 'min'in col_names[c].lower() ]

    def load_provisional_data(self, fname):
        """
        Load datafile from provisional[1]_ data into a Pandas DataFrame
        :param fname: str. Filepath of provisional datafile

        .. _[1] http://andrewsforest.oregonstate.edu/lter/about/weather/portal/
        """
        self.read_header(fname)
        col = self.get_provisional_col(self.header)
        self.load_csv_data(fname, col, skip_nrows=5, time_col=[1])

    def load_ms001_data(self, fname):
        """
        Load datafile from ms001 [1]_ data into a Pandas DataFrame
        :param fname: str. Filepath of ms001 datafile

        .. _[2] : http://andrewsforest.oregonstate.edu/lter/about/weather/hja.cfm?topnav=16
        """
        self.read_header(fname)
        col = self.get_ms001_col(self.header)
        time = self.get_date_time_cols(col)
        self.load_csv_data(fname, col, skip_nrows=1, time_col=time)

class SnotelData(Data_File):
    """
    Class to handle snotel data
    """
    def __init__(self):
        """

        :return:
        """
        Data_File.__init__(self)

    def get_historic_snotel_col(self, header):
        """
        Extract column names from historic snotel[1]_ data header format.
        :param header: array of header lines where each line is a single string.
        :return: array of column names.

        .. _[1] https://wcc.sc.egov.usda.gov/nwcc/tabget
        """
        col = self._get_header_line(header, 58, ',')
        return col

    def load_historic_snotel_data(self, fname):
        """
        Load datafile from historic snotel[1]_ into a Pandas DataFrame
        :param fname: str. Filepath of snotel historic datafile

        .. _[1] https://wcc.sc.egov.usda.gov/nwcc/tabget
        """
        self.read_header(fname, n_lines=59)
        col = self.get_historic_snotel_col(self.header)
        self.load_csv_data(fname, col, skip_nrows=59, time_col=[0])




class MergeData:
    """
    Aggregator class to collect multiple datasets and  merge them together.
    """
    def __init__(self):
        """
        Initialize aggregator class
        """
        self.df = pd.DataFrame()

    def add_provisional_data(self, filename):
        """
        Add an HJA provisional csv to the master dataset
        :param filename: filepath to provisional csv

        Uses self.merge_data to choose the correct method to create an outer
        join based on DateTimeIndex.
        """
        hja = HJ_Data()
        hja.load_provisional_data(filename)

        df = self.merge_data(self.df, hja.data)
        self.df = df

    def add_ms001_data(self, filename):
        """
        Add a csv from the final HJA ms001 database to the master dataset
        :param filename: filepath to provisional csv

        Uses self.merge_data to choose the correct method to create an outer
        join based on DateTimeIndex.
        """
        hja = HJ_Data()
        hja.load_ms001_data(filename)

        df = self.merge_data(self.df, hja.data)
        self.df = df

    def add_historic_snotel_data(self, filename):
        """
        Add a csv dataset historic snotel data to the master dataset.
        :param filename: filepath to the historic snotel dataset

        Uses self.merge_data to choose the correct method to create an outer
        join based on DateTimeIndex.
        """
        snow = SnotelData()
        snow.load_historic_snotel_data(filename)

        df = self.merge_data(self.df, snow.data)
        self.df = df

    def add_hobo_data(self, filename):
        """
        Add a csv dataset generated from .hobo files to the master dataset.
        :param filename: filepath to the hobo dataset

        Uses self.merge_data to choose the correct method to create an outer
        join based on DateTimeIndex.
        """
        hobo = HOBOdata()
        hobo.load_csv_data(filename)

        df = self.merge_data(self.df, hobo.data)
        self.df = df

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
        if data1.empty:
            return data2

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
            #if data1.loc[start:finish, common].empty or data1.loc[start:finish, common].shape[0] < data2[start:finish].shape[0]:
            df = pd.concat([data1, data2], join='outer', ignore_index=False).sort_index()
            #else:
            #   data1[common] = data1[common].fillna(data2[common])
            #   df = data1

        elif self.is_any_columns_common(col1, col2):
            # This means that this is NOT a subset of columns, it is NOT a different set of columns
            # this pertains to partially overlapping column names
            df = pd.concat([data1, data2], join='outer', ignore_index=False)

        sort = df.sort_index()

        return sort

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


if __name__ == "__main__":
    # TEST AGGREGATOR METHOD
    my_path = "c:/workspace/CLIM\\"
    filename = my_path + "CLIM_2016_040.DAT"
    meta = "c:/workspace/CLIM\CLIM_115_header.txt"
    df = CampbellData()
    df.load_cr10_array(filename, meta)
    #
    test = MergeData()
    test.add_toa5_data("c:/workspace/CLIM_113\\2016\CLIM_113_2016_060_Table105.dat")
    test.add_toa5_data("c:/workspace/CLIM_113\\2016\CLIM_113_2016_089_Table105.dat")
    test.add_cr10_data("c:/workspace/CLIM\CLIM_2016_040.DAT", meta,115)
    test.add_cr10_data("c:/workspace/CLIM\CLIM_2016_090.DAT", meta,115)
