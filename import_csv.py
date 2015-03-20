# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from StringIO import StringIO
from csv import reader
from datetime import datetime, date, time
from decimal import Decimal
from trytond.model import fields, ModelSQL, ModelView
from trytond.pool import Pool
from trytond.pyson import Eval, In, Not


__all__ = ['CSVProfile', 'CSVColumnProfile', 'CSVImportLog']


class CSVProfile(ModelSQL, ModelView):
    'CSV Profile'
    __name__ = 'csv.profile'
    name = fields.Char('Name', required=True)
    model = fields.Many2One('ir.model', 'Model', required=True)
    header = fields.Boolean('Header',
        help='Header (field names) on archives')
    separator = fields.Selection([
            (',', 'Comma'),
            (';', 'Semicolon'),
            ('tab', 'Tabulator'),
            ('|', '|'),
            ], 'CSV Separator', help="Archive CSV Separator",
        required=True)
    quote = fields.Char('Quote',
        help='Character to use as quote')
    match_expression = fields.Char('Match Expression',
        help='Eval Python expresion to skip some CSV lines. Example:\n'
            'row[5] == "Cancelled" and row[11] == "user@domain.com"')
    active = fields.Boolean('Active')
    character_encoding = fields.Selection([
            ('utf-8', 'UTF-8'),
            ('latin-1', 'Latin-1'),
            ], 'Character Encoding')
    thousands_separator = fields.Selection([
            ('none', ''),
            ('.', 'Dot (.)'),
            (',', 'Comma (,)'),
            ('others', 'Others'),
            ], 'Thousands Separator', help=("If there are a number the "
                "thousands separator used"),
        required=True)
    decimal_separator = fields.Selection([
            ('.', 'Dot (.)'),
            (',', 'Comma (,)'),
            ], 'Decimal Separator', help=("If there are a number the "
                "decimal separator used"),
        required=True)
    columns = fields.One2Many('csv.column.profile', 'csv_profile', 'Columns')

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_header():
        return True

    @staticmethod
    def default_separator():
        return ";"

    @staticmethod
    def default_quote():
        return '"'

    @classmethod
    def default_character_encoding(cls):
        return 'utf-8'

    @staticmethod
    def default_thousands_separator():
        return "."

    @staticmethod
    def default_decimal_separator():
        return ","

    def read_csv_file(self, archive):
        '''Read CSV data'''
        separator = self.separator
        if separator == "tab":
            separator = '\t'
        quote = self.quote

        data = StringIO(archive)
        if quote:
            rows = reader(data, delimiter=str(separator), quotechar=str(quote))
        else:
            rows = reader(data, delimiter=str(separator))
        return rows


class CSVColumnProfile(ModelSQL, ModelView):
    'CSV Column Profile'
    __name__ = 'csv.column.profile'
    csv_profile = fields.Many2One('csv.profile', 'CSV Profile')
    column = fields.Char('Columns', required=True,
        help='The position of the columns separated by commas corresponding '
        'to this field.')
    field = fields.Many2One('ir.model.field', 'Field',
        domain=[('model.model', '=', 'account.bank.statement.line')],
        select=True, required=True)
    ttype = fields.Function(fields.Char('Field Type'), 'on_change_with_ttype')
    date_format = fields.Char('Date Format',
        states={
            'invisible': Not(In(Eval('ttype'),
                        ['datetime', 'date', 'timestamp', 'time'])),
            'required': In(Eval('ttype'),
                        ['datetime', 'date', 'timestamp', 'time']),
            },
        help='Set the csv format of the DateTime, Date or Timestamp data.\n\n'
            '%d: Day.\t\t\t\t%H: Hours.\n'
            '%m: Month.\t\t\t%M: Minutes.\n'
            '%Y: Year.\t\t\t\t%S: Seconds.\n\n'
            'Use commas to separate more than one field.\n\n'
            'Eg:\n\n%d/%m/%Y,%H:%M:%S\n\n'
            'Will match date and time from two fields like \'13/01/2015\' and '
            '\'17:01:56\'\n\n'
            'To see more information visit: '
            'https://docs.python.org/2/library/datetime.html'
            '?highlight=datetime#strftime-and-strptime-behavior')

    @classmethod
    def __setup__(cls):
        super(CSVColumnProfile, cls).__setup__()
        cls._error_messages.update({
                'columns_must_be_integers':
                    'Columns on field \'%s\' must be integers separated by '
                    'commas.',
                'numeric_format_error': 'Error importing numeric.\n'
                    'Possible causes:\n\n'
                    '\t- The format of the number is wrong.\n'
                    '\t- The csv file has a header and you does not checked '
                    'the box on the wizard.\n\n'
                    'Field: \'%s\'\n'
                    'Value: \'%s\'\n',
                'datetime_format_error': 'Error importing DateTime, Date or '
                    'Time.\n'
                    'Possible causes:\n\n'
                    '\t- The format of the date is wrong.\n'
                    '\t- The csv file has a header and you does not checked '
                    'the box on the wizard.\n\n'
                    'Field: \'%s\'\n'
                    'Value: \'%s\'\n'
                    'Format: \'%s\'',
                'char_encoding_error': 'Error importing Char.\n'
                    'Possible causes:\n\n'
                    '\t- The character encoding of the file is wrong.\n'
                    'Field: \'%s\'\n',
                'integer_too_big_error': 'Error importing integer.\n'
                    'Field \'%s\' has a very big number:\n'
                    'Value: \'%s\'\n'
                    'Value must be between -2147483648 and 2147483647',
                'integer_format_error': 'Error importing integer.\n'
                    'Possible causes:\n\n'
                    '\t- The format of the number is wrong.\n'
                    '\t- The csv file has a header and you does not checked '
                    'the box on the wizard.\n\n'
                    'Field: \'%s\'\n'
                    'Value: \'%s\'\n',
                'boolean_format_error': 'Error importing boolean.\n'
                    'Possible causes:\n\n'
                    '\t- The format of the boolean is wrong.\n'
                    '\t- The csv file has a header and you does not checked '
                    'the box on the wizard.\n\n'
                    'Field: \'%s\'\n'
                    'Value: \'%s\'\n',
                'not_implemented_error': 'This kind of field is not '
                    'implemented yet.'
                })

    @classmethod
    def validate(cls, records):
        super(CSVColumnProfile, cls).validate(records)
        cls.check_columns(records)

    @classmethod
    def check_columns(cls, columns):
        for column in columns:
            cells = column.column.split(',')
            for cell in cells:
                try:
                    int(cell)
                except ValueError:
                    cls.raise_user_error('columns_must_be_integers',
                    error_args=(column.field.name,)
                        )

    @fields.depends('field')
    def on_change_with_ttype(self, name=None):
        if self.field:
            return self.field.ttype

    def get_numeric(self, value):
        thousands_separator = self.csv_profile.thousands_separator
        decimal_separator = self.csv_profile.decimal_separator
        if thousands_separator != 'none':
            value = value.replace(thousands_separator, '')
        if decimal_separator == ',':
            value = value.replace(decimal_separator, '.')
        try:
            value = Decimal(value)
        except:
            self.raise_user_error('numeric_format_error',
                error_args=(self.field.name, value))
        return value

    def get_char(self, value):
        character_encoding = self.csv_profile.character_encoding
        try:
            value = value.decode(character_encoding)
        except:
            self.raise_user_error('char_encoding_error',
                error_args=(self.field.name))
        return value

    def get_integer(self, value):
        try:
            value = int(value)
        except:
            self.raise_user_error('integer_format_error',
                error_args=(self.field.name, value))
        if value < -2147483648 or value > 2147483647:
            self.raise_user_error('integer_too_big_error',
                error_args=(self.field.name, value))
        return value

    def get_datetime(self, value):
        date_format = self.date_format
        try:
            value = datetime.strptime(value, date_format)
        except ValueError:
            self.raise_user_error('datetime_format_error',
                error_args=(self.field.name, value, date_format))
        return value

    def get_date(self, value):
        value = self.get_datetime(value)
        return date(value.year, value.month, value.day)

    def get_time(self, value):
        date_format = self.date_format
        try:
            value = time.strptime(value, date_format)
        except ValueError:
            self.raise_user_error('datetime_format_error',
                error_args=(self.field.name, value, date_format))
        return value

    def get_timestamp(self, value):
        return self.get_datetime(value)

    def get_boolean(self, value):
        try:
            value = bool(value)
        except:
            self.raise_user_error('boolean_format_error',
                error_args=(self.field.name, value))
        return value

    def get_selection(self, value):
        self.raise_user_error('not_implemented_error',
            error_args=(value))

    def get_many2one(self, value):
        self.raise_user_error('not_implemented_error',
            error_args=(value))

    def get_one2many(self, value):
        self.raise_user_error('not_implemented_error',
            error_args=(value))

    def get_value(self, value):
        return getattr(self, 'get_%s' % self.ttype)(value)


class CSVImportLog(ModelSQL, ModelView):
    'CSV Import Log'
    __name__ = 'csv.import.log'
    _rec_name = 'status'
    status = fields.Selection([
            ('done', 'Done'),
            ('skipped', 'Skipped'),
            ], 'Status')
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states={
            'required': True,
            'invisible': True,
            'readonly': True,
            })
    comment = fields.Text('Comment')

    @staticmethod
    def _get_origin():
        'Return list of Model names for origin Reference'
        return ['account.statement']

    @classmethod
    def get_origin(cls):
        IrModel = Pool().get('ir.model')
        models = cls._get_origin()
        models = IrModel.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]
