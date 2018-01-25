# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
try:
    from trytond.modules.import_csv.tests.test_import_csv import suite
except ImportError:
    from .test_import_csv import suite

__all__ = ['suite']
