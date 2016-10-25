=================================
Import CSV Default/Party Scenario
=================================

Imports::

    >>> import os
    >>> from proteus import config, Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.import_csv.tests.tools import read_csv_file

Install party and import_csv::

    >>> config = activate_modules(['party','import_csv'])

Models::

    >>> ImportCSV = Model.get('import.csv')
    >>> ImportCSVColumn = Model.get('import.csv.column')
    >>> Model = Model.get('ir.model')
    >>> Field = Model.get('ir.model.field')
    >>> ImportCSVFile = Model.get('import.csv.file')
    >>> Party = Model.get('party.party')
    >>> Address = Model.get('party.address')

Create Default profile::

    >>> model_party, = Model.find([('model', '=', 'party.party')])
    >>> model_address, = Model.find([('model', '=', 'party.address')])
    >>> model_contact, = Model.find([('model', '=', 'party.contact_mechanism')])
    >>> model_identifier, = Model.find([('model', '=', 'party.identifier')])

    >>> profile = ImportCSV()
    >>> profile.name = 'Test Default'
    >>> profile.header = False
    >>> profile.email = False
    >>> profile.model = model_party
    >>> profile.method = 'default'
    >>> profile.save()

    >>> party_field, = Field.find([('model', '=', model_party.id), ('name', '=', 'name')])
    >>> profile_columns = ImportCSVColumn()
    >>> profile_columns.profile_csv = profile
    >>> profile_columns.column = '1'
    >>> profile_columns.field = party_field
    >>> profile_columns.save()

Create Default import file::

    >>> file_ = ImportCSVFile()
    >>> file_.profile_csv = profile
    >>> filename = os.path.join(os.path.dirname(__file__), 'default.csv')
    >>> file_.csv_file = read_csv_file(filename)
    >>> file_.file_name = 'default.csv'
    >>> file_.save()
    >>> file_.click('import_file')
    >>> parties = Party.find([('name', '=', 'Zikzakmedia')])
    >>> len(parties)
    1

Create Party profile::

    >>> profile2 = ImportCSV()
    >>> profile2.name = 'Test Party'
    >>> profile2.header = False
    >>> profile2.email = False
    >>> profile2.model = model_party
    >>> profile2.method = 'party'
    >>> profile2.save()

    >>> party_field_name, = Field.find([
    ...     ('model', '=', model_party.id), ('name', '=', 'name')])
    >>> profile_columns0 = ImportCSVColumn()
    >>> profile_columns0.profile_csv = profile2
    >>> profile_columns0.column = '0'
    >>> profile_columns0.field = party_field_name
    >>> profile_columns0.save()

    >>> party_field_addresses, = Field.find([
    ...     ('model', '=', model_party.id), ('name', '=', 'addresses')])
    >>> party_field_contact, = Field.find([
    ...     ('model', '=', model_party.id), ('name', '=', 'contact_mechanisms')])
    >>> party_field_identifiers, = Field.find([
    ...     ('model', '=', model_party.id), ('name', '=', 'identifiers')])

    >>> identifier_field_code, = Field.find([
    ...     ('model', '=', model_identifier.id), ('name', '=', 'code')])
    >>> profile_columns1 = ImportCSVColumn()
    >>> profile_columns1.profile_csv = profile2
    >>> profile_columns1.column = '1'
    >>> profile_columns1.field = party_field_identifiers
    >>> profile_columns1.subfield = identifier_field_code
    >>> profile_columns1.save()

    >>> address_field_street, = Field.find([
    ...     ('model', '=', model_address.id), ('name', '=', 'street')])
    >>> profile_columns2 = ImportCSVColumn()
    >>> profile_columns2.profile_csv = profile2
    >>> profile_columns2.column = '2'
    >>> profile_columns2.field = party_field_addresses
    >>> profile_columns2.subfield = address_field_street
    >>> profile_columns2.save()

    >>> address_field_zip, = Field.find([
    ...     ('model', '=', model_address.id), ('name', '=', 'zip')])
    >>> profile_columns3 = ImportCSVColumn()
    >>> profile_columns3.profile_csv = profile2
    >>> profile_columns3.column = '3'
    >>> profile_columns3.field = party_field_addresses
    >>> profile_columns3.subfield = address_field_zip
    >>> profile_columns3.save()

    >>> contact_field_type, = Field.find([
    ...     ('model', '=', model_contact.id), ('name', '=', 'type')])
    >>> profile_columns6 = ImportCSVColumn()
    >>> profile_columns6.profile_csv = profile2
    >>> profile_columns6.column = '6'
    >>> profile_columns6.field = party_field_contact
    >>> profile_columns6.subfield = contact_field_type
    >>> profile_columns6.save()

    >>> contact_field_value, = Field.find([
    ...     ('model', '=', model_contact.id), ('name', '=', 'value')])
    >>> profile_columns7 = ImportCSVColumn()
    >>> profile_columns7.profile_csv = profile2
    >>> profile_columns7.column = '7'
    >>> profile_columns7.field = party_field_contact
    >>> profile_columns7.subfield = contact_field_value
    >>> profile_columns7.save()

Create Party import file::

    >>> file2_ = ImportCSVFile()
    >>> file2_.profile_csv = profile2
    >>> filename = os.path.join(os.path.dirname(__file__), 'party.csv')
    >>> file2_.csv_file = read_csv_file(filename)
    >>> file2_.file_name = 'party.csv'
    >>> file2_.save()
    >>> file2_.click('import_file')
    >>> parties = Party.find([('name', '=', 'Zikzakmedia SL')])
    >>> len(parties)
    1
    >>> addresses = Address.find([('party', '=', 'Zikzakmedia SL')])
    >>> len(addresses)
    2
