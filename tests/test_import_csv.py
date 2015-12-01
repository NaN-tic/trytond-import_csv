# This file is part of the import_csv module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class ImportCsvTestCase(ModuleTestCase):
    'Test Import Csv module'
    module = 'import_csv'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ImportCsvTestCase))
    return suite