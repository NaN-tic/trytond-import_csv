# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from email.header import Header
from email.mime.text import MIMEText
from io import StringIO
from csv import reader
from datetime import datetime, date, time
from decimal import Decimal
from trytond.config import config
from trytond.model import fields, ModelSQL, ModelView
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, In, Not
from trytond.pyson import PYSON, PYSONEncoder, PYSONDecoder
from trytond.sendmail import sendmail
from trytond.transaction import Transaction

__all__ = ['ImportCSV', 'ImportCSVColumn', 'ImportCSVFile']


class ImportCSV(ModelSQL, ModelView):
    'Import CSV'
    __name__ = 'import.csv'
    name = fields.Char('Name', required=True)
    model = fields.Many2One('ir.model', 'Model', required=True)
    header = fields.Boolean('CSV Header',
        help='Set this check box if CSV file has a header.')
    email = fields.Boolean('Email',
        help='Send email after import data')
    separator = fields.Selection([
            (',', 'Comma'),
            (';', 'Semicolon'),
            ('tab', 'Tabulator'),
            ('|', '|'),
            ], 'CSV Separator', required=True,
        help="Field separator in CSV lines.")
    quote = fields.Char('CSV Quote',
        help='Character to use as a quote of strings.')
    method = fields.Selection('get_method', 'Method',
        required=True)
    match_expression = fields.Char('Exclude Rows',
        help='Eval Python expression to skip some CSV lines, it will exclude '
            'all rows matching this criteria. Example:\n'
            'row[5] == "Cancelled" and row[11] == "user@domain.com"\n')
    active = fields.Boolean('Active')
    character_encoding = fields.Selection([
            ('utf-8', 'UTF-8'),
            ('latin-1', 'Latin-1'),
            ], 'CSV Character Encoding')
    thousands_separator = fields.Selection([
            ('none', ''),
            ('.', 'Dot (.)'),
            (',', 'Comma (,)'),
            ('others', 'Others'),
            ], 'CSV Thousand Separator', required=True,
        help="Thousand separator used when there is a number.")
    decimal_separator = fields.Selection([
            ('.', 'Dot (.)'),
            (',', 'Comma (,)'),
            ], 'CSV Decimal Separator', required=True,
        help="Decimal separator used when there is a number.")
    columns = fields.One2Many('import.csv.column', 'profile_csv', 'Columns')

    @classmethod
    def get_method(cls):
        '''CSV Methods'''
        pool = Pool()

        res = [('default', 'Default')]

        try:
            Party = pool.get('party.party')
            res.append(('party', 'Party'))
        except KeyError:
            pass

        try:
            Product = pool.get('product.product')
            res.append(('product', 'Product'))
        except KeyError:
            pass

        try:
            Product = pool.get('sale.sale')
            res.append(('sale', 'Sale'))
        except KeyError:
            pass

        return res

    @staticmethod
    def default_method():
        return 'default'

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_header():
        return True

    @staticmethod
    def default_email():
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


class ImportCSVColumn(ModelSQL, ModelView):
    'Import CSV Column'
    __name__ = 'import.csv.column'
    profile_csv = fields.Many2One('import.csv', 'Import CSV', required=True,
        ondelete='CASCADE')
    column = fields.Char('Columns', required=False, states={
            'invisible': Bool(Eval('constant'))
            },
        help='The position of the CSV columns separated by commas '
            'to get the content of this field. First one is 0.')
    constant = fields.Char('Constant', states={
            'invisible': Bool(Eval('column'))
            },
        help='A constant value to set in this field.',)
    field = fields.Many2One('ir.model.field', 'Field',
        domain=[('model', '=', Eval('_parent_profile_csv', {}).get('model'))],
        select=True, required=True)
    field_type = fields.Function(fields.Char('Field Type'),
        'on_change_with_field_type')
    submodel = fields.Function(fields.Many2One('ir.model', 'Submodel'),
        'on_change_with_submodel')
    subfield = fields.Many2One('ir.model.field', 'Subfield',
        domain=[('model', '=', Eval('submodel'))],
        states={
            'invisible': ~Eval('field_type').in_(
                ['one2many', 'many2many']),
            'required': Eval('field_type').in_(
                ['one2many', 'many2many']),
        }, depends=['field_type', 'submodel'], select=True)
    ttype = fields.Function(fields.Char('Field Type'), 'on_change_with_ttype')
    date_format = fields.Char('Date Format',
        states={
            'invisible': Not(In(Eval('ttype'),
                    ['datetime', 'date', 'timestamp', 'time', 'many2one',
                        'one2many', 'many2many'])),
            'required': In(Eval('ttype'),
                ['datetime', 'date', 'timestamp', 'time']),
            },
        help='Set the CSV format of the DateTime, Date or Timestamp data.\n\n'
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
    add_to_domain = fields.Boolean('Add to Domain',
        help='If checked, adds this field to domain for searching records in '
            'order to avoid duplicates.')
    selection = fields.Text('Selection', states={
            'invisible': Eval('ttype') != 'selection',
            }, depends=['ttype'],
        help='A couple of key and value separated by ":" per line')

    @classmethod
    def __setup__(cls):
        super(ImportCSVColumn, cls).__setup__()
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
                    '"Constant" fields of line %s can not be empty at the '
                    'ame time. Please fill at least one of them.',
                })

    @fields.depends('field')
    def on_change_with_field_type(self, name=None):
        if self.field:
            return self.field.ttype
        return ''

    @fields.depends('field', '_parent_profile_csv.model')
    def on_change_with_submodel(self, name=None):
        Model = Pool().get('ir.model')

        if getattr(self, 'profile_csv'):
            profile_model = self.profile_csv.model
        elif 'model' in Transaction().context:
            profile_model = Model(Transaction().context.get('model'))
        else:
            return None

        ProfileModel = Pool().get(profile_model.model)

        if (self.field and
                self.field.ttype in ['many2one', 'one2many', 'many2many']):
            field = ProfileModel._fields[self.field.name]
            relation = field.get_target().__name__
            models = Model.search([('model', '=', relation)])
            return models[0].id if models else None
        return None

    @classmethod
    def validate(cls, records):
        super(ImportCSVColumn, cls).validate(records)
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
            # Python3 strings can not be decoded
            if hasattr(value, 'decode'):
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

    def get_many2one(self, values):
        Model = Pool().get(self.field.relation)
        records = Model.search([
            ('name', '=', values[0]),
            ])
        if records:
            return record[0]
        else:
            return

    def get_one2many(self, values):
        return values[0]

    def get_many2many(self, values):
        # TODO
        pass

    def get_value(self, values):
        if values and values[0]:
            return getattr(self, 'get_%s' % self.ttype)(values)
        elif self.constant:
            return getattr(self, 'get_%s' % self.ttype)([self.constant])


class ImportCSVFile(ModelSQL, ModelView):
    'Import CSV File'
    __name__ = 'import.csv.file'
    _rec_name = 'id'
    profile_csv = fields.Many2One('import.csv', 'Profile CSV', required=True,
        states={
            'readonly': (Eval('state') != 'draft')
        }, depends=['state'])
    csv_file = fields.Binary('CSV File to import', required=True, filename='file_name',
        states={
            'readonly': (Eval('state') != 'draft')
        }, depends=['state'])
    file_name = fields.Char('File Name', required=True,
        states={
            'readonly': (Eval('state') != 'draft')
        }, depends=['state'])
    skip_repeated = fields.Boolean('Skip Repeated',
        states={
            'readonly': (Eval('state') != 'draft')
        }, depends=['state'],
        help='If any record of the CSV file is already imported, skip it.')
    update_record = fields.Boolean('Update Record',
        states={
            'readonly': (Eval('state') != 'draft')
        }, depends=['state'],
        help='If any record of the CSV file is found with the search domain, '
            'update the record.')
    date_ = fields.DateTime('Date', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('error', 'Error'),
        ('done', 'Done'),
        ], 'State', states={
            'readonly': True,
            })

    @classmethod
    def __setup__(cls):
        super(ImportCSVFile, cls).__setup__()
        cls._order.insert(0, ('date_', 'DESC'))
        cls._order.insert(1, ('id', 'DESC'))
        cls._error_messages.update({
                'csv_format_error': 'Please, check that the CSV file '
                    'configuration matches with the format of the CSV file.',
                'record_already_exists': 'Record %s skipped. '
                    'Already exists.',
                'record_added': 'Record %s added.',
                'record_updated': 'Record %s updated.',
                'email_subject': 'CSV Import result',
                'user_email_error': '%s has not any email address',
                'import_successfully': 'Successfully imported %s records.',
                'import_unsuccessfully': 'Unsuccessfully imported %s records.'
                    'Check configuration profile or CSV file',
                })
        cls._buttons.update({
                'import_file': {
                    'invisible': (Eval('state') == 'done'),
                    },
                })

    @classmethod
    def default_state(cls):
        return 'draft'

    @staticmethod
    def default_date_():
        return datetime.now()

    @classmethod
    def prepare_message(cls):
        User = Pool().get('res.user')

        user = User(Transaction().user)

        to_addr = user.email or config.get('email', 'from')
        if not to_addr:
            return
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
        if to_addr:
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

        file_ = self.csv_file
        # On python3 we must convert the binary file to string
        if hasattr(file_, 'decode'):
            file_ = file_.decode(self.profile_csv.character_encoding)
        data = StringIO(file_)
        if quote:
            rows = reader(data, delimiter=str(separator), quotechar=str(quote))
        else:
            rows = reader(data, delimiter=str(separator))
        data.close()
        return rows

    @classmethod
    def add_message_line(cls, csv_file, status, error_message, error_args):
        return '%(time)s:\t%(profile)s (%(profile_id)s)\t%(filename)s\t%(status)s\t%(message)s' % {
            'time': datetime.now(),
            'profile': csv_file.profile_csv.rec_name,
            'profile_id': csv_file.profile_csv.id,
            'filename': csv_file.file_name,
            'status': status,
            'message': cls.raise_user_error(
                error_message,
                error_args=error_args,
                raise_exception=False),
            }

    @classmethod
    def import_file_default(cls, csv_file):
        '''Default Import CSV'''
        pool = Pool()

        profile_csv = csv_file.profile_csv
        model = profile_csv.model
        has_header = profile_csv.header
        skip_repeated = csv_file.skip_repeated
        update_record = csv_file.update_record

        Model = pool.get(model.model)

        data = csv_file.read_csv_file()
        if has_header:
            next(data, None)

        logs = []
        to_save = []
        for row in data:
            if not row:
                continue

            domain = []
            values = {}
            for column in profile_csv.columns:
                # each column, get value and assign in dict
                if column.constant:
                    value = column.constant
                else:
                    cells = column.column.split(',')
                    try:
                        vals = [row[int(c)] for c in cells if c]
                    except IndexError:
                        cls.raise_user_error('csv_format_error')
                    value = column.get_value(vals)

                if column.add_to_domain:
                    domain.append((column.field.name, '=', value))

                values[column.field.name] = value

            if domain:
                # search record exist
                records = Model().search(domain, limit=1)

                if skip_repeated and records:
                    logs.append(cls.add_message_line(
                        csv_file,
                        'skipped',
                        'record_already_exists',
                        (records[0].rec_name,)))
                    continue

                if update_record and records:
                    record, = records # to update
                    logs.append(cls.add_message_line(
                        csv_file,
                        'done',
                        'record_updated',
                        (values)))
                else:
                    record = Model() # to create
                    logs.append(cls.add_message_line(
                        csv_file,
                        'done',
                        'record_added',
                        (values)))
            else:
                record = Model() # to create
                logs.append(cls.add_message_line(
                    csv_file,
                    'done',
                    'record_added',
                    (values)))

            # assign values to object record
            for k, v in values.iteritems():
                setattr(record, k, v)
            to_save.append(record)

        state = 'done'
        if to_save:
            try:
                Model.save(to_save)
                logs.insert(0, cls.add_message_line(
                    csv_file,
                    'done',
                    'import_successfully',
                    (len(to_save),)))
            except:
                state = 'error'
                logs.insert(0, cls.add_message_line(
                    csv_file,
                    'error',
                    'import_unsuccessfully',
                    (len(to_save),)))

        cls.write([csv_file], {'state': state})
        Transaction().commit() # force to commit

        if profile_csv.email:
            cls.send_message('\n'.join(logs))

    @classmethod
    def import_file_party(cls, csv_file):
        '''Party Import CSV'''
        pool = Pool()

        profile_csv = csv_file.profile_csv
        has_header = profile_csv.header
        skip_repeated = csv_file.skip_repeated
        update_record = csv_file.update_record

        Party = pool.get('party.party')
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        PartyIdentifier = pool.get('party.identifier')

        data = csv_file.read_csv_file()
        if has_header:
            next(data, None)

        # Create a new list with parent and child values for each record
        # Group CSV lines in same record. See party.csv example in test
        # rows = [{
        #    'record': {},
        #    'domain': [],
        #    }
        rows = []
        for row in data:
            is_party = True
            is_address = False
            is_contact = False

            identifiers = []
            domain = []
            values = {}
            for column in profile_csv.columns:
                # each column, get value and assign in dict
                cells = column.column.split(',')
                cell = int(cells[0])

                if column.constant:
                    value = column.constant
                else:
                    try:
                        vals = [row[int(c)] for c in cells if c]
                    except IndexError:
                        cls.raise_user_error('csv_format_error')
                    value = column.get_value(vals)

                if column.field.name == 'addresses' and row[cell]:
                    is_address = True
                    is_party = False
                    values[column.subfield.name] = value
                    if column.add_to_domain:
                        domain.append(('addresses.'+column.subfield.name, '=', value))
                    continue
                elif column.field.name == 'contact_mechanisms' and row[cell]:
                    is_contact = True
                    is_party = False
                    values[column.subfield.name] = value
                    if column.add_to_domain:
                        domain.append(('contact_mechanisms.'+column.subfield.name, '=', value))
                    continue
                elif column.field.name == 'identifiers' and row[cell]:
                    identifiers.append({'code': value})
                elif row[cell]:
                    values[column.field.name] = value
                    domain.append((column.field.name, '=', value))

            # add values in rows
            if is_address and values:
                rows[-1]['record']['addresses'].append(values)
                if domain:
                    rows[-1]['domain'].append(domain)
            elif is_contact and values:
                rows[-1]['record']['contact_mechanisms'].append(values)
                if domain:
                    rows[-1]['domain'].append(domain)
            elif is_party and values:
                values['addresses'] = []
                values['contact_mechanisms'] = []
                values['identifiers'] = identifiers
                rows.append({
                    'record': values,
                    'domain': domain if domain else None,
                    })

        # convert dict values to object and save
        logs = []
        to_save = []
        for row in rows:
            domain = row['domain']
            data = row['record']

            addresses = data['addresses']
            del data['addresses']
            contact_mechanisms = data['contact_mechanisms']
            del data['contact_mechanisms']
            identifiers = data['identifiers']
            del data['identifiers']

            # search record exist (party)
            if domain:
                records = Party.search(domain, limit=1)

                if skip_repeated and records:
                    logs.append(cls.add_message_line(
                        csv_file,
                        'skipped',
                        'record_already_exists',
                        (records[0].rec_name,)))
                    continue

                if update_record and records:
                    record, = records # to update
                    logs.append(cls.add_message_line(
                        csv_file,
                        'done',
                        'record_updated',
                        (row)))
                else:
                    record = Party() # to create
                    logs.append(cls.add_message_line(
                        csv_file,
                        'done',
                        'record_added',
                        (row)))
            else:
                record = Party() # to create
                logs.append(cls.add_message_line(
                    csv_file,
                    'done',
                    'record_added',
                    (row)))

            # assign values to object record
            # (party, address, contact mechanism and identifier)
            for k, v in data.iteritems():
                setattr(record, k, v)
            if not hasattr(record, 'addresses'):
                record.addresses = ()
            if not hasattr(record, 'contact_mechanisms'):
                record.contact_mechanisms = ()
            if not hasattr(record, 'identifiers'):
                record.identifiers = ()

            addrs = ()
            for addr in addresses:
                address = Address()
                for k, v in addr.iteritems():
                    setattr(address, k, v)
                address.on_change_country()
                try: # country_zip
                    address.on_change_zip()
                except:
                    pass
                addrs += (address,)
            if addrs:
                record.addresses += addrs

            cms = ()
            for cm in contact_mechanisms:
                contact = ContactMechanism()
                for k, v in cm.iteritems():
                    setattr(contact, k, v)
                cms += (contact,)
            if cms:
                record.contact_mechanisms += cms

            idens = ()
            for iden in identifiers:
                identifier = PartyIdentifier()
                for k, v in iden.iteritems():
                    setattr(identifier, k, v)
                idens += (identifier,)
            if idens:
                record.identifiers += idens

            to_save.append(record) # to save

        state = 'done'
        if to_save:
            try:
                Party.save(to_save)
                logs.insert(0, cls.add_message_line(
                    csv_file,
                    'done',
                    'import_successfully',
                    (len(to_save),)))
            except:
                state = 'error'
                logs.insert(0, cls.add_message_line(
                    csv_file,
                    'error',
                    'import_unsuccessfully',
                    (len(to_save),)))

        cls.write([csv_file], {'state': state})
        Transaction().commit() # force to commit

        if profile_csv.email:
            cls.send_message('\n'.join(logs))

    @classmethod
    def import_file_sale(cls, csv_file):
        '''Sale Import CSV'''
        pool = Pool()

        profile_csv = csv_file.profile_csv
        has_header = profile_csv.header
        skip_repeated = csv_file.skip_repeated
        update_record = csv_file.update_record

        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')
        Product = pool.get('product.product')

        data = csv_file.read_csv_file()
        if has_header:
            next(data, None)

        # Create a new list with parent and child values for each record
        # Group CSV lines in same record. See party.csv example in test
        # rows = [{
        #    'record': {},
        #    'domain': [],
        #    }
        rows = []
        for row in data:
            is_sale = True
            is_line = False

            domain = []
            values = {}
            for column in profile_csv.columns:
                # each column, get value and assign in dict
                cells = column.column.split(',')
                cell = int(cells[0])

                if column.constant:
                    value = column.constant
                else:
                    try:
                        vals = [row[int(c)] for c in cells if c]
                    except IndexError:
                        cls.raise_user_error('csv_format_error')
                    value = column.get_value(vals)

                if column.field.name == 'line' and row[cell]:
                    is_line = True
                    is_sale = False
                    if column.subfield.name == 'product':
                        products = Product.search([
                            ('rec_name', '=', value),
                            ])
                        if products:
                            values[column.subfield.name] = value
                        else:
                            values['description'] = value
                    if column.add_to_domain:
                        domain.append(('lines.'+column.subfield.name, '=', value))
                    continue
                elif row[cell]:
                    values[column.field.name] = value
                    domain.append((column.field.name, '=', value))

            # add values in rows
            if is_line and values:
                rows[-1]['record']['lines'].append(values)
                if domain:
                    rows[-1]['domain'].append(domain)
            elif is_sale and values:
                values['lines'] = []
                rows.append({
                    'record': values,
                    'domain': domain if domain else None,
                    })

        # convert dict values to object and save
        logs = []
        to_save = []
        for row in rows:
            domain = row['domain']
            data = row['record']

            lines = data['lines']
            del data['lines']

            # search record exist (party)
            if domain:
                records = Sale.search(domain, limit=1)

                if skip_repeated and records:
                    logs.append(cls.add_message_line(
                        csv_file,
                        'skipped',
                        'record_already_exists',
                        (records[0].rec_name,)))
                    continue

                if update_record and records:
                    record, = records # to update
                    logs.append(cls.add_message_line(
                        csv_file,
                        'done',
                        'record_updated',
                        (row)))
                else:
                    record = Sale() # to create
                    logs.append(cls.add_message_line(
                        csv_file,
                        'done',
                        'record_added',
                        (row)))
            else:
                record = Sale() # to create
                logs.append(cls.add_message_line(
                    csv_file,
                    'done',
                    'record_added',
                    (row)))

            # assign values to object record
            # (sale and line)
            for k, v in data.iteritems():
                setattr(record, k, v)
            if not hasattr(record, 'lines'):
                record.lines = ()

            sale_lines = ()
            for l in lines:
                line = Line()
                for k, v in l.iteritems():
                    setattr(line, k, v)
                line.on_change_product()
                sale_lines += (line,)
            if sale_lines:
                record.lines += sale_lines

            to_save.append(record) # to save

        state = 'done'
        if to_save:
            try:
                Sale.save(to_save)
                logs.insert(0, cls.add_message_line(
                    csv_file,
                    'done',
                    'import_successfully',
                    (len(to_save),)))
            except:
                state = 'error'
                logs.insert(0, cls.add_message_line(
                    csv_file,
                    'error',
                    'import_unsuccessfully',
                    (len(to_save),)))

        cls.write([csv_file], {'state': state})
        Transaction().commit() # force to commit

        if profile_csv.email:
            cls.send_message('\n'.join(logs))

    @classmethod
    @ModelView.button
    def import_file(cls, csv_files):
        '''Import CSV'''
        for csv_file in csv_files:
            profile_csv = csv_file.profile_csv
            import_csv = getattr(cls, 'import_file_%s' %
                profile_csv.method)
            import_csv(csv_file)
