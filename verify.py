# date: 3/15/16
# created by: Greg Cohn
__authors__='Greg Cohn'

import pandas as pd
import matplotlib.pyplot as plt

class CampbellData:
    """
    Load and process data from Campbell scientific loggers.

    """

    def __init__(self):
        """

        :return:
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

        :param file_name:
        :param n_lines:
        :return:
        """
        f = open(file_name)
        header = [f.next() for l in range(0, n_lines)]
        f.close()

        self.header = header

    def _get_header_line(self, header, lineno):
        """

        :param header:
        :param lineno:
        :return:
        """
        line = [s.strip('"') for s in header[lineno].strip().split(',')]
        return line

    def get_toa5_col(self, header):
        """

        :param header:
        :return:
        """
        col = self._get_header_line(header, 1)
        return col

    def get_toa5_units(self, header):
        """

        :param header:
        :return:
        """
        units = self._get_header_line(header, 2)
        return units

    def get_toa5_collection_method(self, header):
        """

        :param header:
        :return:
        """
        meth = self._get_header_line(header, 3)
        return meth

    def get_toa5_prog(self, header):
        """

        :param header:
        :return:
        """

        return header[0].split(',')[5].strip('"')

    def get_toa5_os(self, header):
        """

        :param header:
        :return:
        """
        return header[0].split(',')[4].strip('"')


    def get_toa5_progid(self, header):
        """

        :param header:
        :return:
        """
        return header[0].split(',')[6]

    def get_toa5_logger(self, header):
        """

        :param header:
        :return:
        """
        return header[0].split(',')[2]

    def load_csv_data(self, fname, col, skip_nrows=4):
        """

        :param header:
        :param skip_nrows:
        :return:
        """
        self.data = pd.read_csv(fname, skiprows=4, names=col, parse_dates=True, index_col=0)

    def load_toa5_data(self, fname):
        """

        :param fname:
        :return:
        """
        self.read_header(fname)
        col = self.get_toa5_col(self.header)
        self.load_csv_data(fname, col)

class HOBOdata:
    """

    """
    def __init__(self):
        """

        :return:
        """

class MergeHoboToa5:
    """

    """
    def __init__(self):
        """

        :return:
        """
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
        self._reset_value(pump_off, 'PUMP_ON', -1)
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

class CompareData:
    """

    """
    def __init__(self, filename):
        """

        :return:
        """
        dat = CampbellData()
        dat.load_toa5_data(filename)

        self.data = dat.data

    def get_data_lim(self, data, buffer=0.1):
        """
        Evaluates all data in a dataframe, and returns the max and min of all values with a buffer. The default buffer
        is 0.1 (10%)

        :param data: a Pandas DataFrame containing the columns and indexes(rows) to be evaluated
        :param buffer: The method will return the limits plus a buffer. The max value + buffer and the min value -
        buffer. Defaults to 0.1 (10%)
        :return: tuple of min, max values.
        """
        high = max(data.max())
        low = min(data.min())
        range = high-low
        high += range * 0.1
        low -= range * 0.1

        return low, high

    def plot_scatter_matrix(self, columns):
        """

        :param columns:
        :return:
        """
        data = self.data[columns]
        ax = pd.scatter_matrix(data)

        return ax

    def get_diff_sensors(self, columns):
        """

        :param columns:
        :return:
        """
        data = self.data[columns]
        diffs = data.diff(axis=1)

        return diffs[columns[1:]]

    def plot_compare_sensors(self, columns, units):

        data = self.data[columns]

        ax1 = plt.subplot(2,1,1)
        x = columns[0]
        y = columns[1:]
        lines = plt.plot(data[x], data[y], '.')
        plt.legend(lines, columns[1:])

        plt.xlabel(x)
        plt.ylabel(units)
        plt.grid('on')
        plt.hold('on')

        low, high = self.get_data_lim(data)
        plt.plot([low, high], [low, high], '-k')

        ax2 = plt.subplot(2,1,2)
        diffs = self.get_diff_sensors(columns)
        plt.plot(data[x], diffs, '.')

        plt.xlabel(x)
        plt.ylabel(units)
        plt.grid('on')
        plt.hold('on')

        plt.plot([low, high], [0, 0], '-k')



if __name__ == "__main__":
    my_path = "c:/workspace/"
    # "E:\DATA\METDAT\CENMET/"
    #
    # 'E:\workspace\pump_controls\\verrification'
    # #\\TOA5_UPLO_235_CONT_20160229.dat'    #'C:\Users\gcohn\Google Drive\work\pump_controls\\TOA5_UPLO_235_CONT_20160229.dat'
    filename = my_path + "RS02\\2016\\090\\RS02_090_2016_109.dat"
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

    # Test new Trigger call
    trig = PumpOperations(filename)
    trig.check_values()

    # Test Time Series Offset
    # off = OffsetTriggerTs(trig.cont)
    # off.offset_dataframe()
    # off.concat_trig_to_offset()

    trig.offset_trigger_ts()
    trig.graph_controls(trig.cont_offset)