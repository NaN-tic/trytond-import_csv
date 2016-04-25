# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from email.header import Header
from email.mime.text import MIMEText
from io import BytesIO
from csv import reader
from datetime import datetime, date, time
from decimal import Decimal
import logging
from trytond.config import config
from trytond.model import fields, ModelSQL, ModelView
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, In, Not
from trytond.pyson import PYSON, PYSONEncoder, PYSONDecoder
from trytond.sendmail import sendmail
from trytond.transaction import Transaction

import unicodedata

__all__ = ['ProfileCSV', 'ProfileCSVColumn', 'ImportCSVFile']

logger = logging.getLogger(__name__)


class ProfileCSV(ModelSQL, ModelView):
    'Profile CSV'
    __name__ = 'profile.csv'
    name = fields.Char('Name', required=True)
    model = fields.Many2One('ir.model', 'Model', required=True)
    header = fields.Boolean('Header',
        help='Header (field names) on csv files')
    separator = fields.Selection([
            (',', 'Comma'),
            (';', 'Semicolon'),
            ('tab', 'Tabulator'),
            ('|', '|'),
            ], 'CSV Separator', help="File CSV Separator",
        required=True)
    quote = fields.Char('Quote',
        help='Character to use as quote')
    match_expression = fields.Char('Match Expression',
        help='Eval Python expresion to skip some CSV lines. Example:\n'
            'row[5] == "Cancelled" and row[11] == "user@domain.com"\n'
            'Will exclude all rows matching this criteria.')
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
    columns = fields.One2Many('profile.csv.column', 'profile_csv', 'Columns')

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_header():
        return True

    @staticmethod
    def default_separator():
        return ","

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


class ProfileCSVColumn(ModelSQL, ModelView):
    'Profile CSV Column'
    __name__ = 'profile.csv.column'
    profile_csv = fields.Many2One('profile.csv', 'Profile CSV', required=True,
        ondelete='CASCADE')
    column = fields.Char('Column', required=False, states={
            'invisible': Bool(Eval('constant'))
            },
        help='The position of the columns separated by commas corresponding '
        'to this field.')
    constant = fields.Char('Constant', states={
            'invisible': Bool(Eval('column'))
            },
        help='A constant value to set in this field.',)
    field = fields.Many2One('ir.model.field', 'Field',
        domain=[('model', '=', Eval('_parent_profile_csv', {}).get('model'))],
        select=True, required=True)
    ttype = fields.Function(fields.Char('Field Type'), 'on_change_with_ttype')
    date_format = fields.Char('Date Format',
        states={
            'invisible': Not(In(Eval('ttype'),
                    ['datetime', 'date', 'timestamp', 'time', 'many2one',
                        'one2many', 'many2many'])),
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
    search_record_code = fields.Text('Search Record Code', states={
            'invisible': Not(In(Eval('ttype'),
                    ['many2one', 'one2many', 'many2many'])),
            },
        help='Type the python code for mapping this field.\n'
            'You can use:\n'
            '  * self: To make reference to this mapping record.\n'
            '  * pool: To make reference to the data base objects.\n'
            '  * values: List of values. There is one for each column selected'
                ' on field "Columns". Useful when you want concatenate strings'
                ' of various columns in one field, or when you want use more '
                'than one value as a criteria to search in many2one or *2many '
                'fields.\n'
            'You must assign the result to a variable called "result".')
    add_to_domain = fields.Boolean('Add to Search Domain',
        help='If checked, adds this field to domain for searching records in '
            'order to avoid duplications.')
    selection = fields.Text('Selection', states={
            'invisible': Eval('ttype') != 'selection',
            }, depends=['ttype'],
        help='A couple of key and value separated by ":" per line')

    @classmethod
    def __setup__(cls):
        super(ProfileCSVColumn, cls).__setup__()
        cls._order = [
            ('column', 'ASC'),
            ('id', 'DESC'),
            ]
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
                'column_and_constant_null_error': 'The "Columns" and '
                    '"Constant" fields of line %s can not be empty at a time. '
                    'Please fill at least one of them.',
                })

    @classmethod
    def validate(cls, records):
        super(ProfileCSVColumn, cls).validate(records)
        cls.check_sources(records)
        cls.check_columns(records)

    @classmethod
    def check_sources(cls, columns):
        for column in columns:
            if not column.column and not column.constant:
                cls.raise_user_error('column_and_constant_null_error',
                    error_args=(column.field.name,)
                        )

    @classmethod
    def check_columns(cls, columns):
        for column in columns:
            cells = column.column
            if not cells:
                continue
            cells = cells.split(',')
            for cell in cells:
                try:
                    int(cell)
                except ValueError:
                    cls.raise_user_error('columns_must_be_integers',
                    error_args=(column.field.name,)
                        )

    @staticmethod
    def default_add_to_domain():
        return True

    def field_required(self):
        field = Pool().get(self.field.model.model)
        return (field._fields[self.field.name].required
            or field._fields[self.field.name].states.get('required', False))

    @fields.depends('field')
    def on_change_with_ttype(self, name=None):
        if self.field:
            return self.field.ttype

    @property
    def digits(self):
        digits = 4
        if self.field.ttype in ('float', 'numeric'):
            Model = Pool().get(self.field.model.model)
            digits = Model._fields.get(self.field.name).digits[1]
            if isinstance(digits, PYSON):
                digits = PYSONDecoder().decode(PYSONEncoder().encode(digits))
        return digits

    def get_numeric(self, values):
        for value in values:
            quantize = Decimal(10) ** -Decimal(self.digits)
            thousands_separator = self.profile_csv.thousands_separator
            decimal_separator = self.profile_csv.decimal_separator
            if thousands_separator != 'none':
                value = value.replace(thousands_separator, '')
            if decimal_separator == ',':
                value = value.replace(decimal_separator, '.')
            try:
                value = Decimal(value).quantize(quantize)
            except:
                self.raise_user_error('numeric_format_error',
                    error_args=(self.field.name, value))
            return value

    def get_char(self, values):
        result = ''
        for value in values:
            character_encoding = self.profile_csv.character_encoding
            try:
                value = value.decode(character_encoding)
            except:
                self.raise_user_error('char_encoding_error',
                    error_args=(self.field.name))
            if result:
                result += ', ' + value
            else:
                result = value
        return result

    def get_text(self, values):
        return self.get_char(values)

    def get_integer(self, values):
        for value in values:
            try:
                value = int(value)
            except:
                self.raise_user_error('integer_format_error',
                    error_args=(self.field.name, value))
            if value < -2147483648 or value > 2147483647:
                self.raise_user_error('integer_too_big_error',
                    error_args=(self.field.name, value))
            return value

    def get_datetime(self, values):
        for value in values:
            date_format = self.date_format
            try:
                value = datetime.strptime(value, date_format)
            except ValueError:
                self.raise_user_error('datetime_format_error',
                    error_args=(self.field.name, value, date_format))
            return value

    def get_date(self, values):
        value = self.get_datetime(values)
        return date(value.year, value.month, value.day)

    def get_time(self, values):
        for value in values:
            date_format = self.date_format
            try:
                value = time.strptime(value, date_format)
            except ValueError:
                self.raise_user_error('datetime_format_error',
                    error_args=(self.field.name, value, date_format))
            return value

    def get_timestamp(self, values):
        return self.get_datetime(values)

    def get_boolean(self, values):
        for value in values:
            try:
                value = bool(value)
            except:
                self.raise_user_error('boolean_format_error',
                    error_args=(self.field.name, value))
            return value

    def get_selection(self, values):
        value = self.get_char([values[0]])
        map_values = self.selection or u''
        if map_values:
            for pair in map_values.splitlines():
                if pair:
                    key, map_value = pair.split(':')
                    if key == value:
                        value = map_value.strip()
                        break
        return value

    def get_result(self, values):
        localspace = {
            'self': self,
            'pool': Pool(),
            'values': values,
        }
        try:
            exec self.search_record_code in localspace
        except (SyntaxError, KeyError) as e:
            logger.error('Syntax Error in mapping %s field.'
                ' Error: %s' %
                (self.field.name, e))
            return False
        except NameError, e:
            logger.error('Name Error in mapping %s field.'
                ' Error: %s' %
                (self.field.name, e))
            return False
        except AssertionError:
            logger.error('Assertion Error in mapping %s field.'
                % self.field.name)
            return False
        except Exception, e:
            logger.error('Unknown Error in mapping %s field.'
                ' Message: %s' %
                (self.field.name, e))
            return False
        return localspace['result'] if 'result' in localspace else None

    def get_many2one(self, values):
        if self.search_record_code:
            return self.get_result(values) or None

    def get_one2many(self, values):
        if self.search_record_code:
            return self.get_result(values) or None

    def get_many2many(self, values):
        if self.search_record_code:
            return self.get_result(values) or None

    def get_value(self, values):
        if values and values[0]:
            return getattr(self, 'get_%s' % self.ttype)(values)
        elif self.constant:
            return getattr(self, 'get_%s' % self.ttype)([self.constant])

    def get_field_value(self, **kvargs):
        Model = Pool().get(self.profile_csv.model.model)
        kvargs['field'] = self.field.name
        kvargs['csv_column'] = self
        get_field_value = getattr(Model, 'get_field_value')
        if not get_field_value:
            self.raise_user_error('not_implemented_error')
        return get_field_value(**kvargs)


class ImportCSVFile(ModelSQL, ModelView):
    'Import CSV File'
    __name__ = 'import.csv.file'
    profile_csv = fields.Many2One('profile.csv', 'CSV',
        required=True)
    csv_file = fields.Binary('CSV File', required=True)
    skip_repeated = fields.Boolean('Skip Repeated',
        help='If any record of the CSV file is already imported, skip it.')
    update_record = fields.Boolean('Update Record',
        help='If any record of the CSV file is already found with search '
            'domain, update records.')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ], 'State', states={
            'readonly': True,
            })

    @classmethod
    def __setup__(cls):
        super(ImportCSVFile, cls).__setup__()
        cls._error_messages.update({
                'general_failure': 'Please, check that the CSV file is '
                    'effectively a CSV file.',
                'csv_format_error': 'Please, check that the CSV file '
                    'configuration matches with the format of the CSV file.',
                'database_general_failure': 'Database general failure.\n'
                    'Error raised: %s.',
                'record_already_exists_error': 'Record %s skipped. '
                    'Already exists.',
                'record_already_has_lines':
                    'You cannot import a CSV record because "%s" '
                    'have lines.',
                'record_not_draft':
                    'You cannot import a CSV record because "%s" '
                    'is not draft state.',
                'required_field_null_error': 'Field %s is required but not '
                    'value found in record %s. Record skipped!',
                'skip_row_filter_error':
                    'Row %s skipped by "Exclude Row" filter rule.',
                'not_implemented_error': 'This kind of domain is not '
                    'implemented yet.',
                'match_expression_error': 'Error in Match Expression Domain. '
                    'Error raised: %s',
                'record_added': 'Record %s added.',
                'record_updated': 'Record %s updated.',
                'email_subject': 'CSV Import result',
                'user_email_error': '%s has not any email address',
                'functional_field_error': 'Functional field %s has not setter '
                    'method.',
                })
        cls._buttons.update({
                'import_file': {
                    'invisible': Eval('state') != 'draft',
                    },
                })

    @classmethod
    def default_skip_repeated(cls):
        return True

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def prepare_message(cls):
        User = Pool().get('res.user')
        user = User(Transaction().user)

        to_addr = user.email or config.get('email', 'from')
        if not to_addr:
            cls.raise_user_error('user_email_error', error_args=(user.name,))

        return to_addr

    @classmethod
    def create_message(cls, from_addr, to_addrs, subject, message):
        msg = MIMEText(message, _charset='utf-8')
        msg['To'] = ', '.join(to_addrs)
        msg['From'] = from_addr
        msg['Subject'] = Header(subject, 'utf-8')
        return msg

    @classmethod
    def send_message(cls, message):
        to_addr = cls.prepare_message()
        from_addr = config.get('email', 'uri')
        subject = cls.raise_user_error('email_subject', raise_exception=False)
        msg = cls.create_message(from_addr, [to_addr], subject, message)
        sendmail(from_addr, [to_addr], msg)

    def read_csv_file(self):
        '''Read CSV data'''
        separator = self.profile_csv.separator
        if separator == "tab":
            separator = '\t'
        quote = self.profile_csv.quote

        data = BytesIO(self.csv_file)
        if quote:
            rows = reader(data, delimiter=str(separator), quotechar=str(quote))
        else:
            rows = reader(data, delimiter=str(separator))
        return rows

    @classmethod
    @ModelView.button
    def import_file(cls, csv_files):
        pool = Pool()

        def add_message_line(profile_csv, status, error_message, error_args):
            return (str(datetime.now()) + ':\t' +
                'profile.csv,%s' % profile_csv.id + '\t' +
                status + '\t' +
                cls.raise_user_error(
                    error_message,
                    error_args=error_args,
                    raise_exception=False) + '\n'
                )

        to_create = []
        to_update = []
        for csv_file in csv_files:
            message = ''
            profile_csv = csv_file.profile_csv
            model = profile_csv.model
            Model = pool.get(model.model)
            has_header = profile_csv.header
            skip_repeated = csv_file.skip_repeated
            update_record = csv_file.update_record

            data = csv_file.read_csv_file()

            if has_header:
                next(data, None)

            for row in list(data):
                if not row:
                    continue
                values = {}
                domain = []
                for column in profile_csv.columns:
                    cells = column.column.split(',')
                    try:
                        vals = [row[int(c)] for c in cells if c]
                    except IndexError:
                        cls.raise_user_error('csv_format_error')

                    field = Model._fields[column.field.name]
                    if (getattr(field, 'getter', None)
                            and not getattr(field, 'setter', None)):
                        cls.raise_user_error('functional_field_error',
                            error_args=column.field.name,
                            raise_exception=True)

                    value = column.get_value(vals)
                    if value is None and column.field_required():
                        message += add_message_line('skipped',
                            row, 'required_field_null_error',
                            (profile_csv, column))
                        break
                    elif column.profile_csv.match_expression:
                        try:
                            match = eval(column.profile_csv.match_expression)
                        except (NameError, TypeError, IndexError) as e:
                            message += add_message_line(profile_csv,
                                'skipped', 'match_expression_error', (e,))
                            break
                        if match:
                            message += add_message_line(profile_csv,
                                'skipped', 'skip_row_filter_error', (row))
                            break

                    values[column.field.name] = value

                    if column.field.name and column.add_to_domain:
                        if column.ttype in ('one2many', 'many2many'):
                            operator = 'in'
                            if value[0][0] == 'add':
                                value = value[0][1]
                            elif value[0][0] == 'create':
                                Relation = pool.get(column.field.relation)
                                val = []
                                for record in value[0][1]:
                                    dom = []
                                    for field in record:
                                        dom.append((field, '=', record[field]))
                                    val += [r.id for r in Relation.search(dom)]
                                value = val
                            else:
                                cls.raise_user_error('not_implemented_error',
                                    raise_exception=True)
                        else:
                            operator = '='

                        domain.append((
                                column.field.name.encode('utf-8'),
                                operator,
                                value,
                                ))
                else:
                    if domain:
                        records = Model.search(domain)

                        if update_record and records:
                            for record in records:
                                for field in values:
                                    setattr(record, field, values[field])
                            to_update.extend(records)
                            message += add_message_line(profile_csv,
                                'done', 'record_updated', (values))
                        else:
                            if skip_repeated and records:
                                message += add_message_line(profile_csv,
                                    'skipped', 'record_already_exists_error',
                                    (records[0].rec_name,))
                                continue
                            else:
                                to_create.append(Model(**values))
                            message += add_message_line(profile_csv,
                                'done', 'record_added', (values))
                    else:
                        to_create.append(Model(**values))
                        message += add_message_line(profile_csv,
                            'done', 'record_added', (values))

            if to_create:
                Model.save(to_create)

            if to_update:
                Model.save(to_update)

            cls.send_message(message)
        cls.write(csv_files, {'state': 'done'})
