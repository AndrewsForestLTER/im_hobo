"""Sample-in/sample-out tests for the TOA5 and Parquet output writers.

Builds a small HOBOdata instance directly (bypassing raw HOBO CSV parsing) to
isolate the writer boundary -- both writers consume the same cleaned
self.data/self.col that reformat_HOBO_csv produces.
"""
import pandas as pd
import pytz
import pyarrow.parquet as pq

import hobo_qaqc


def build_sample_hobodata():
    q = hobo_qaqc.HOBOdata(logs=[])
    dates = pd.to_datetime([
        '2024-06-01 00:00:00',
        '2024-06-01 00:15:00',
        '2024-06-01 00:30:00',
    ]).tz_localize(pytz.FixedOffset(-480))
    q.data = pd.DataFrame({
        'Date': dates,
        'Temp': pd.array([12.5, float('nan'), 13.25], dtype='float32'),
        'Intensity': pd.array([100.0, 200.5, float('nan')], dtype='float64'),
    })
    q.col = ['Date', 'Temp', 'Intensity']
    return q


def test_export_to_toa5(tmp_path):
    q = build_sample_hobodata()
    out = tmp_path / 'sample.dat'

    q.export_to_toa5(
        out, station='MS045', logger_model='HOBO-Pendant', serial='12345',
        table_name='Table1', sitecode='PA002',
    )

    lines = out.read_text().splitlines()
    assert lines[0] == '"TOA5","MS045","HOBO-Pendant","12345","","","","Table1"'
    assert lines[1] == '"TIMESTAMP","RECORD","Sitecode","Temp","Intensity"'
    assert lines[2] == '"TS","RN","","Deg C","lux"'
    assert lines[3] == '"","","Smp","Smp","Smp"'
    assert lines[4] == '"2024-06-01 00:00:00",0,"PA002",12.5,100'
    assert lines[5] == '"2024-06-01 00:15:00",1,"PA002",NAN,200.5'
    assert lines[6] == '"2024-06-01 00:30:00",2,"PA002",13.25,NAN'


def test_export_to_toa5_sitecode_defaults_to_empty_string(tmp_path):
    q = build_sample_hobodata()
    out = tmp_path / 'sample.dat'

    q.export_to_toa5(out)

    lines = out.read_text().splitlines()
    assert lines[1] == '"TIMESTAMP","RECORD","Sitecode","Temp","Intensity"'
    assert lines[4] == '"2024-06-01 00:00:00",0,"",12.5,100'


def test_export_to_toa5_serial_defaults_to_source_header(tmp_path):
    q = build_sample_hobodata()
    q.serial = '9948811'  # normally set by load_csv_data() from the raw HOBO header
    out = tmp_path / 'sample.dat'

    q.export_to_toa5(out, station='MS045', table_name='Table1')

    lines = out.read_text().splitlines()
    assert lines[0] == '"TOA5","MS045","","9948811","","","","Table1"'


def test_export_to_toa5_explicit_serial_overrides_source_header(tmp_path):
    q = build_sample_hobodata()
    q.serial = '9948811'
    out = tmp_path / 'sample.dat'

    q.export_to_toa5(out, serial='CONFIG_OVERRIDE')

    lines = out.read_text().splitlines()
    assert lines[0] == '"TOA5","","","CONFIG_OVERRIDE","","","",""'


def test_get_csv_serial_number_parses_lgr_sn():
    # Verbatim column-header line from a HOBOWARE bulk export.
    header_line = (
        '"#","Date Time, GMT-07:00","Temp, \xb0F (LGR S/N: 9948811, SEN S/N: 9948811)",'
        '"Intensity, lum/ft\xb2 (LGR S/N: 9948811, SEN S/N: 9948811)",'
        '"Bad Battery (LGR S/N: 9948811)","Coupler Attached (LGR S/N: 9948811)",'
        '"Stopped (LGR S/N: 9948811)","End Of File (LGR S/N: 9948811)"'
    )
    q = hobo_qaqc.HOBOdata(logs=[])
    assert q.get_csv_serial_number([header_line]) == '9948811'


def test_get_csv_serial_number_absent_returns_empty_string():
    q = hobo_qaqc.HOBOdata(logs=[])
    assert q.get_csv_serial_number(['"#","Date Time, GMT-07:00","Temp, \xb0F"']) == ''


def test_export_to_parquet_roundtrip(tmp_path):
    q = build_sample_hobodata()
    out = tmp_path / 'sample.parquet'

    q.export_to_parquet(out, sitecode='PA002')
    result = pd.read_parquet(out)

    assert list(result.columns) == ['Date', 'Sitecode', 'Temp', 'Intensity']
    assert (result['Sitecode'] == 'PA002').all()
    assert pd.api.types.is_datetime64_any_dtype(result['Date'])
    assert result['Date'].dt.tz is not None
    assert result['Temp'].dtype == 'float32'
    assert result['Intensity'].dtype == 'float64'

    pd.testing.assert_series_equal(
        result['Date'].dt.tz_convert('UTC').reset_index(drop=True),
        q.data['Date'].dt.tz_convert('UTC').reset_index(drop=True),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['Temp'].reset_index(drop=True), q.data['Temp'].reset_index(drop=True),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['Intensity'].reset_index(drop=True), q.data['Intensity'].reset_index(drop=True),
        check_names=False,
    )


def test_export_to_parquet_sitecode_defaults_to_empty_string(tmp_path):
    q = build_sample_hobodata()
    out = tmp_path / 'sample.parquet'

    q.export_to_parquet(out)
    result = pd.read_parquet(out)

    assert list(result.columns) == ['Date', 'Sitecode', 'Temp', 'Intensity']
    assert (result['Sitecode'] == '').all()


def test_export_to_parquet_embeds_units_metadata(tmp_path):
    q = build_sample_hobodata()
    out = tmp_path / 'sample.parquet'

    q.export_to_parquet(out)
    schema = pq.read_schema(out)

    assert schema.field('Date').metadata is None
    assert schema.field('Temp').metadata[b'units'] == b'Deg C'
    assert schema.field('Intensity').metadata[b'units'] == b'lux'
