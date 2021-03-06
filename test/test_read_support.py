import csv
import json
import os
from io import BytesIO, StringIO
import tempfile
import unittest

import parquet


class TestFileFormat(unittest.TestCase):
    def test_header_magic_bytes(self):
        main = parquet.ParquetMain()
        with tempfile.NamedTemporaryFile() as t:
            t.write(b"PAR1_some_bogus_data")
            t.flush()
            self.assertTrue(main._check_header_magic_bytes(t))

    def test_footer_magic_bytes(self):
        main = parquet.ParquetMain()
        with tempfile.NamedTemporaryFile() as t:
            t.write(b"PAR1_some_bogus_data_PAR1")
            t.flush()
            self.assertTrue(main._check_footer_magic_bytes(t))

    def test_not_parquet_file(self):
        main = parquet.ParquetMain()
        with tempfile.NamedTemporaryFile() as t:
            t.write(b"blah")
            t.flush()
            self.assertFalse(main._check_header_magic_bytes(t))
            self.assertFalse(main._check_footer_magic_bytes(t))


class TestMetadata(unittest.TestCase):

    f = "test-data/nation.impala.parquet"

    def test_footer_bytes(self):
        main = parquet.ParquetMain()
        with open(self.f, 'rb') as fo:
            self.assertEquals(327, main._get_footer_size(fo))

    def test_read_footer(self):
        main = parquet.ParquetMain()
        footer = main.read_footer(self.f)
        self.assertEquals(
            set([s.name for s in footer.schema]),
            set(["schema", "n_regionkey", "n_name", "n_nationkey",
                 "n_comment"]))

    def test_dump_metadata(self):
        data = BytesIO()
        main = parquet.ParquetMain()
        main.dump_metadata(self.f, data)


class Options(object):

    def __init__(self, col=None, format='csv', no_headers=True, limit=-1):
        self.col = col
        self.format = format
        self.no_headers = no_headers
        self.limit = limit


class TestReadApi(unittest.TestCase):

    def test_projection(self):
        pass

    def test_limit(self):
        pass

class TestCompatibility(unittest.TestCase):

    td = "test-data"
    nation_csv = os.path.join(td, "nation.csv")
    parquets = ["gzip-nation.impala.parquet", "nation.dict.parquet",
                "nation.impala.parquet", "nation.plain.parquet",
                "snappy-nation.impala.parquet"]

    def _compare_data(self, expected_data, actual_data):
        assert expected_data == actual_data

    def _test_file_csv(self, parquet_file, csv_file):
        """ Given the parquet_file and csv_file representation, converts the
            parquet_file to a csv using the dump utility and then compares the
            result to the csv_file.
        """
        expected_data = []
        with open(csv_file, 'r') as f:
            expected_data = list(csv.reader(f, delimiter='|'))

        main = parquet.ParquetMain()
        actual_raw_data = StringIO()
        main.dump(parquet_file, Options(), out=actual_raw_data)
        actual_raw_data.seek(0, 0)
        actual_data = list(csv.reader(actual_raw_data, delimiter='\t'))

        self._compare_data(expected_data, actual_data)

        actual_raw_data = StringIO()
        main.dump(parquet_file, Options(no_headers=False),
                     out=actual_raw_data)
        actual_raw_data.seek(0, 0)
        actual_data = list(csv.reader(actual_raw_data, delimiter='\t'))[1:]

        self._compare_data(expected_data, actual_data)

    def _test_file_json(self, parquet_file, csv_file):
        """ Given the parquet_file and csv_file representation, converts the
            parquet_file to json using the dump utility and then compares the
            result to the csv_file using column agnostic ordering.
        """
        expected_data = []
        with open(csv_file, 'r') as f:
            expected_data = list(csv.reader(f, delimiter='|'))

        actual_raw_data = StringIO()
        main = parquet.ParquetMain()
        main.dump(parquet_file, Options(format='json'),
                     out=actual_raw_data)
        actual_raw_data.seek(0, 0)
        actual_data = [json.loads(x.rstrip()) for x in
                       actual_raw_data.read().split("\n") if len(x) > 0]

        assert len(expected_data) == len(actual_data)
        footer = main.read_footer(parquet_file)
        cols = [s.name for s in footer.schema]
        for expected, actual in zip(expected_data, actual_raw_data):
            assert len(expected) == len(actual)
            for i, c in enumerate(cols):
                if c in actual:
                    assert expected[i] == actual[c]

    def _test_file_custom(self, parquet_file, csv_file):
        """ Given the parquet_file and csv_file representation, converts the
            parquet_file to json using the dump utility and then compares the
            result to the csv_file using column agnostic ordering.
        """
        expected_data = []
        with open(csv_file, 'r') as f:
            expected_data = list(csv.reader(f, delimiter='|'))
        main = parquet.ParquetMain()

        def _custom_datatype(in_dict, keys):
            '''
            return rows like the csv outputter

            Could convert to a dataframe like this:
                import pandas
                df = pandas.DataFrame(in_dict)
                return df
            '''
            columns = [in_dict[key] for key in keys]
            rows = zip(*columns)
            return [x for x in rows]

        actual_data = main.dump(parquet_file, Options(format='custom'), out=_custom_datatype)
        assert len(expected_data) == len(actual_data)
        footer = main.read_footer(parquet_file)
        cols = [s.name for s in footer.schema]

        for expected, actual in zip(expected_data, actual_data):
            assert len(expected) == len(actual)
            for i, c in enumerate(cols):
                if c in actual:
                    assert expected[i] == actual[c]

    def test_all_files(self):
        self.files = [(os.path.join(self.td, p), self.nation_csv) for p in self.parquets]
        for parquet_file, csv_file in self.files:
            self._test_file_csv(parquet_file, csv_file)
            self._test_file_json(parquet_file, csv_file)
            self._test_file_custom(parquet_file, csv_file)
