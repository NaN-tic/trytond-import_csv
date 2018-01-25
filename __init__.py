# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import import_csv


def register():
    Pool.register(
        import_csv.ImportCSV,
        import_csv.ImportCSVColumn,
        import_csv.ImportCSVFile,
        module='import_csv', type_='model')
