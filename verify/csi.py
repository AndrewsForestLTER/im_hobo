# coding=utf-8
import pandas as pd
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
            t = int(r[1])
            j = int(r[0])
            y = int(r[2])

            len = str(t).__len__()
            HHMM = str(t)
            while len<4:
                HHMM = '0' + HHMM
                len = HHMM.__len__()

            HHMM = '0000' if t == 2400 else HHMM
            ymax = 366 if (y % 4 == 0 and y % 100!= 0) or y % 400 == 0 else 365
            j = j+1 if t == 2400 and j <= ymax else j
            j = 1 if j > ymax and t == 2400 else j
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
        julian_day, time = self.get_cr10_to_HHMM(data[['JulianDay', 'Time', 'Year']])
        ts = pd.to_datetime(data.Year.astype(str) + ' ' + julian_day + ' ' + time, format='%Y %j %H%M')
        self.data = data.set_index(ts)

if __name__ == "__main__":
    # TEST CONT Table load
    my_path = 'E:\workspace\pump_controls\\verrification'
    filename = my_path + '\\TOA5_UPLO_235_CONT_20160229.dat'

    # Test Time Series Offset
    cont = CampbellData()
    cont.load_toa5_data(filename)

    # TEST CR10 Load
    my_path = "c:/workspace/CLIM\\"
    filename = my_path + "CLIM_2016_040.DAT"
    meta = "c:/workspace/CLIM\CLIM_115_header.txt"
    df = CampbellData()
    df.load_cr10_array(filename, meta)

    # TEST TOA5 105 table load
    my_path = "c:/workspace/"
    filename = my_path + "RS02\\2016\\090\\RS02_090_2016_109.dat"
    rs = CampbellData()
    rs.load_toa5_data(filename)

    #TEST Provisional Data Load
    uplo = CampbellData()
    uplo.load_provisional_data('E:\workspace\Power\UPLO_intermediate_radio\uplmet_236_5min_2016_0705.csv')