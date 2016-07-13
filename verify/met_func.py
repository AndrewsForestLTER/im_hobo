from load_data import MergeData
import pandas as pd
import matplotlib.pyplot as plt
from scipy import integrate as integrate
from numpy import isnan, diff

# date: 7/06/16
# created by: Greg Cohn
__authors__ = 'Greg Cohn'
__version__ = '0.1'


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
    def __init__(self, df):
        """

        :return:
        """

        self.cont = df
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


class SolarPower:
    """
    Assess parameters for solar power systems: power generation and system power needs.
    """

    def __init__(self, df, col=['BATTERY_AVG', 'SOLAR_MEAN_100_0_01']):
        """
        Initialize SolarPower with a DataFrame containing columns with battery information, and columns with solar
        information.
        :param df: pandas DataFrame containing information on battery voltage and solar W
        :param col: array of str. Column names for battery and solar measurements
        brief explanation about pyranometer
        """

        self.col = col
        self.df_5min = df
        find_day = df[col[1]] > 0
        self.day = df[find_day]
        self.night = df[~find_day]

    def calculate_sun_hours(self):
        """
        Calculate the hours of sun for each calender day in SolarPower.day
        :return: A pandas Series containing time delta objects for hours of sunlight daily
        """

        day_dict ={'dawn': self.get_dawn_dusk('dawn')}
        day_dict['dusk'] = self.get_dawn_dusk('dusk')
        dawn2dusk = pd.DataFrame(day_dict, index=day_dict['dawn'])

        return dawn2dusk['dusk'] - dawn2dusk['dawn']

    def integrate_kW(self, col='SOLAR_MEAN_100_0_01'):
        """
        Preform a trapezoidal integration, calculating area between observed data points. Returns a Series of area
        values measured in kJ
        :param col: str to index the column in a Pandas DataFrame
        :return: a Pandas Series containing kJ and time
        """

        df = self.df_5min

        # cannot preform integral on nan data
        no_nan = ~isnan(df[col])
        # time data must be in monotonically increasing values. To integrate kW to kJ, the values must be in seconds
        t = (df.index[no_nan] - df.index.min()).total_seconds()
        kj = diff(integrate.cumtrapz(df.loc[no_nan, col], t, initial=0))

        return pd.Series(kj, index=df[no_nan].index[1:])

    def get_periodic_sum_kj(self, kj, interval='1d'):
        """
        Calculate the kj released over a known period, both as a total.
        :param kj: a Pandas Series containing kJ for each segment of datapoints (NOT cumulative)
        :param interval: str defining the interval to summarize data on (uses pandas.resample())
        :return:returns a pandas Series of total kJ at the defined interval.
        """

        kj_sum = kj.resample(interval, closed='right', axis=0).sum()

        return kj_sum

    def get_mean_kj(self, kj, avg_interval='1d', group_by='1m'):
        """
        Calculate mean kj for a defined interval, summarized at a defined time step.
        :param kj: A pandas DataFrame containing the sum of kj for a time step
        :param avg_interval: The interval to average the data. See pandas format_. Keyword default '1d' (daily average)
        :param group_by: The time step for summarizing the data. See pandas format_
        :return: pandas DataFrame containing mean kj

        .. Example::
            ###Mean daily kJ displayed by month

            'get_mean_kj(kj, avg_interval='1d', group_by='1m')`

            Out[90]:
            Date
            2016-01-31    2.256325e+06
            2016-02-29    4.953275e+06
            2016-03-31    7.287097e+06
            2016-04-30    1.462466e+07
            2016-05-31    1.658091e+07
            2016-06-30    2.155054e+07
            2016-07-31    1.924648e+07
            Freq: M, dtype: float64

            'get_mean_kj(kj, avg_interval='1m', group_by='1Q')`

            ###Mean monthly kJ displayed by Q
            Out[91]:
            Date
            2016-03-31    1.464970e+08
            2016-06-30    5.330881e+08
            2016-09-30    1.732183e+08
            Freq: Q-DEC, dtype: float64

        .. _format : https://pythonprogramming.net/resample-data-analysis-python-pandas-tutorial/
        """
        kj_sum = self.get_periodic_sum_kj(kj, interval=avg_interval)
        kj_avg = kj_sum.resample(group_by, closed='right', axis=0).mean()

        return kj_avg

    def j_to_whr(self, values):
        """
        Convert Joules to Watt hours.
        :param values: value or array of values to be converted
        :return: converted value or array of values

        A Watt is a Joule / second, so that a Joule can be defined as the work to transport 1 W of power for 1 sec of
        time, or a Watt second (Ws). The amount of work to transport 1 W of power for 1 hour is a Watt hour (Wh). Since
        1 J = 1 Ws, to convert to Wh:
        1 Ws = 1 Ws * 1 min/60 sec * 1 hr/60 min = 1 Ws * 1/3600 = 1J/3600 = 0.000278 Wh
        or
        1 Wh = 1 J/1 sec *1hr * 60 sec/1 min * 60 min/1 hour =  1 J * 3600
        """

        return values/3600

    def get_dawn_dusk(self, method):
        """
        Use daytime values to identify the time of sunrise and sunset.
        :param method: str defining the sampling method used. Accepts: 'dawn','min','sunrise','dusk','max','sunset'.
        :return: array of datetime values.

        .. Note::
            This method identifies the first or last time stamp in each 24 hour period. This requires that the DataFrame
            assessed only contains daytime values, i.e. values with pyranometer readings >0. The value will not
            match astronomical dawn exactly, and will fluctuate with cloud cover, vegetative shading (i.e. green up),
            and topographic position of the site.
        """
        day = self.day
        day['Date'] = day.index.values

        lmethod = method.lower()
        if lmethod in 'dawn min sunrise':
            timestamps = day['Date'].resample('24h', closed='right', axis=0).min()
        elif lmethod in 'dusk max sunset':
            timestamps = day['Date'].resample('24h', closed='right', axis=0).max()

        return pd.to_datetime(timestamps.values)


if __name__ == "__main__":
    # TEST Data Comparison
    rs = CompareData('Hourly_Avg_RS_05')
    header = "c:/workspace/RS05\\2016\\005\RS05_115_Header.dat"
    cr10_dat = "c:/workspace/RS05\\2016\\005\RS05_2016_140.dat"
    cr1k_dat = "c:/workspace/RS05\\2016\\092\RS05_092_2016_140.dat"
    rs.add_cr10_data(cr10_dat, header, 115)
    rs.add_toa5_data(cr1k_dat)

    rs.df = rs.df.resample('1H', label='right', closed='right', how='mean')
    rs.plot_compare_sensors(['AIR_01_AVG','AIR_02_Avg', 'AIR_03_Avg'], "$^{\circ}$ C")

    my_path = 'E:\workspace\pump_controls\\verrification'
    filename = my_path + '\\TOA5_UPLO_235_CONT_20160229.dat'

    from verify import csi
    # Test Time Series Offset
    cont = csi.CampbellData()
    cont.load_toa5_data(filename)

    off = OffsetTriggerTs(cont.data)
    off.offset_dataframe()
    off.concat_trig_to_offset()

    # TEST NEW TRIGGER TABLE CALL
    trig = PumpOperations(filename)
    trig.check_values()

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
