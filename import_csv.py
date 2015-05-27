# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from StringIO import StringIO
from csv import reader
from datetime import datetime, date, time
from decimal import Decimal
import logging
from trytond.model import fields, ModelSQL, ModelView
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, In, Not
from trytond.wizard import Button, StateTransition, StateView, Wizard


__all__ = ['ProfileCSV', 'ProfileCSVColumn', 'ImportCSVLog',
    'ImportCSVStart', 'ImportCSV']


class ProfileCSV(ModelSQL, ModelView):
    'Profile CSV'
    __name__ = 'profile.csv'
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
    columns = fields.One2Many('profile.csv.column', 'profile_csv', 'Columns')

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


class ProfileCSVColumn(ModelSQL, ModelView):
    'Profile CSV Column'
    __name__ = 'profile.csv.column'
    profile_csv = fields.Many2One('profile.csv', 'Profile CSV', required=True)
    column = fields.Char('Columns', required=False, states={
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
            '  * value: The value of this field.\n'
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

    def field_required(self):
        field = Pool().get(self.field.model.model)
        return (field._fields[self.field.name].required
            or field._fields[self.field.name].states.get('required', False))

    @fields.depends('field')
    def on_change_with_ttype(self, name=None):
        if self.field:
            return self.field.ttype

    def get_numeric(self, value):
        thousands_separator = self.profile_csv.thousands_separator
        decimal_separator = self.profile_csv.decimal_separator
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
        character_encoding = self.profile_csv.character_encoding
        try:
            value = value.decode(character_encoding)
        except:
            self.raise_user_error('char_encoding_error',
                error_args=(self.field.name))
        return value

    def get_text(self, value):
        return self.get_char(value)

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
        value = self.get_char(value)
        map_values = self.selection or u''
        if map_values:
            for pair in map_values.splitlines():
                if pair:
                    key, map_value = pair.split(':')
                    if key == value:
                        value = map_value.strip()
                        break
        return value

    def get_result(self, value):
        logger = logging.getLogger('import_csv')
        localspace = {
            'self': self,
            'pool': Pool(),
            'value': value,
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

    def get_many2one(self, value):
        if self.search_record_code:
            return self.get_result(value) or None

    def get_one2many(self, value):
        if self.search_record_code:
            return self.get_result(value) or None

    def get_many2many(self, value):
        if self.search_record_code:
            return self.get_result(value) or None

    def get_value(self, value):
        if value:
            return getattr(self, 'get_%s' % self.ttype)(value)
        elif self.constant:
            return getattr(self, 'get_%s' % self.ttype)(self.constant)


class ImportCSVLog(ModelSQL, ModelView):
    'Import CSV Log'
    __name__ = 'import.csv.log'
    _rec_name = 'status'
    status = fields.Selection([
            ('done', 'Done'),
            ('skipped', 'Skipped'),
            ], 'Status',
        states={
            'readonly': True,
            })
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states={
            'required': True,
            'invisible': True,
            'readonly': True,
            })
    comment = fields.Text('Comment', states={
            'readonly': True,
            })
    date_time = fields.DateTime('Date and Time', states={
            'readonly': True,
            })
    parent = fields.Many2One('import.csv.log', 'Parent', states={
            'invisible': True,
            'readonly': True,
            },
        )
    children = fields.One2Many('import.csv.log', 'parent', 'Log Lines',
        states={
            'readonly': True,
            })

    @classmethod
    def __setup__(cls):
        super(ImportCSVLog, cls).__setup__()
        cls._order.insert(0, ('date_time', 'DESC'))

    @staticmethod
    def _get_origin():
        'Return list of Model names for origin Reference'
        return ['profile.csv']

    @classmethod
    def get_origin(cls):
        IrModel = Pool().get('ir.model')
        models = cls._get_origin()
        models = IrModel.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]


class ImportCSVStart(ModelView):
    'Import CSV start'
    __name__ = 'import.csv.start'
    profile_csv = fields.Many2One('profile.csv', 'CSV',
        required=True)
    import_file = fields.Binary('Import File', required=True)
    header = fields.Boolean('Headers',
        help='Set this check box to true if CSV file has headers.')
    attachment = fields.Boolean('Attachment',
        help='Attach CSV file after import.')
    character_encoding = fields.Selection([
            ('utf-8', 'UTF-8'),
            ('latin-1', 'Latin-1'),
            ], 'Character Encoding')
    skip_repeated = fields.Boolean('Skip Repeated',
        help='If any record of the csv file is already imported, skip it.')

    @classmethod
    def default_profile_csv(cls):
        ProfileCSV = Pool().get('profile.csv')
        profile_csvs = ProfileCSV.search([])
        if len(profile_csvs) == 1:
            return profile_csvs[0].id

    @classmethod
    def default_skip_repeated(cls):
        return True

    @classmethod
    def default_attachment(cls):
        return True

    @classmethod
    def default_character_encoding(cls):
        ProfileCSV = Pool().get('profile.csv')
        profile_csvs = ProfileCSV.search([])
        if len(profile_csvs) == 1:
            return profile_csvs[0].character_encoding
        return 'utf-8'

    @fields.depends('profile_csv')
    def on_change_profile_csv(self):
        changes = {}
        if self.profile_csv:
            changes['character_encoding'] = (
                self.profile_csv.character_encoding)
        return changes


class ImportCSV(Wizard):
    'Import CSV'
    __name__ = 'import.csv'
    start = StateView('import.csv.start', 'import_csv.import_csv_start', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Import File', 'import_file', 'tryton-ok', default=True),
            ])
    import_file = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ImportCSV, cls).__setup__()
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
                })

    def transition_import_file(self):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        profile_csv = self.start.profile_csv
        model = profile_csv.model
        Model = pool.get(model.model)
        import_file = self.start.import_file
        has_header = self.start.header
        has_attachment = self.start.attachment
        skip_repeated = self.start.skip_repeated

        data = profile_csv.read_csv_file(import_file)

        if has_header:
            next(data, None)

        vlist = []
        log_values = []
        for row in list(data):
            if not row:
                continue
            values = {}
            domain = []
            for column in profile_csv.columns:
                cells = column.column.split(',')
                try:
                    value = ','.join(row[int(c)] for c in cells if c)
                except IndexError:
                    self.raise_user_error('csv_format_error')
                value = column.get_value(value)

                if value is None and column.field_required():
                    log_value = {
                        'date_time': datetime.now(),
                        }
                    log_value['origin'] = 'profile.csv,%s' % profile_csv.id
                    log_value['comment'] = self.raise_user_error(
                        'required_field_null_error',
                        error_args=(column.field.field_description, row),
                        raise_exception=False)
                    log_value['status'] = 'skipped'
                    log_values.append(log_value)
                    break
                elif (column.profile_csv.match_expression
                        and eval(column.profile_csv.match_expression)):
                    log_value = {
                        'date_time': datetime.now(),
                        }
                    log_value['origin'] = 'profile.csv,%s' % profile_csv.id
                    log_value['comment'] = self.raise_user_error(
                        'skip_row_filter_error',
                        error_args=(row),
                        raise_exception=False)
                    log_value['status'] = 'skipped'
                    log_values.append(log_value)
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
                            self.raise_user_error('not_implemented_error',
                                raise_exception=True)
                    else:
                        operator = '='
                    domain.append((
                            column.field.name,
                            operator,
                            value
                            ))
            else:
                if skip_repeated and domain:
                    records = Model.search(domain)
                    if records:
                        log_value = {
                            'date_time': datetime.now(),
                            }
                        log_value['origin'] = 'profile.csv,%s' % profile_csv.id
                        log_value['comment'] = self.raise_user_error(
                            'record_already_exists_error',
                            error_args=(records[0].rec_name,),
                            raise_exception=False)
                        log_value['status'] = 'skipped'
                        log_values.append(log_value)
                        continue

                if skip_repeated:
                    skip = len(vlist) != 0
                    for vals in vlist:
                        skip = True
                        for field in values:
                            skip &= vals[field] == values[field]
                        if skip:
                            break
                    if skip:
                        continue

                log_value = {
                    'date_time': datetime.now(),
                    }
                log_value['origin'] = 'profile.csv,%s' % profile_csv.id
                log_value['comment'] = ('Record %s added.' % (values))
                log_value['status'] = 'done'
                log_values.append(log_value)
                vlist.append(values)
        if vlist:
            Model.create(vlist)

        csv_log, = ImportCSVLog.create([{
                'date_time': datetime.now(),
                'origin': 'profile.csv,%s' % profile_csv.id,
                'comment': '%s %s' % (profile_csv.name, datetime.now()),
                'status': 'done',
                'children': [
                    ('create', log_values),
                    ],
                }])

        if has_attachment:
            attach = Attachment(
                name=datetime.now().strftime("%y/%m/%d %H:%M:%S"),
                type='data',
                data=import_file,
                resource=str(csv_log))
            attach.save()

        return 'end'
