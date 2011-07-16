import time
import bl.vl.utils as vlu
import itertools as it
import numpy     as np

class EAVAdapter(object):
  """
  FIXME
  """

  EAV_EHR_TABLE = 'eav_ehr_table.h5'

  EAV_STORAGE_COLS = \
  [('long', 'timestamp', 'When this row was written', None),
   ('string', 'i_vid',
    """an unique identifier that points to the kb object (typically an
    individual) related to this record. This is actually redundant,
    since it should be possible to recover it by looking at the target
    of the action identified by a_vid. It is kept as a convenience,
    but it is a responsability of the user app to keep data consistent.
    """,
    len(vlu.make_vid()), None),
    ('string', 'a_vid',
    """a unique identifier that points to the Action that generates the
    record (a single Action can generate several records. We need the
    Action to know how data was collected, when it was collected and where)""",
    len(vlu.make_vid()), None),
   ('bool', 'valid',
    """nothing will be deleted, so we keep a flag to know if the record
    is a valid one and if we can use it""", None),
   ('string', 'g_vid',
    """a grouper used to group records together""",
    len(vlu.make_vid()), None),
   ('string', 'archetype',
    """the Archetype we used to represent the data we are collecting
    so that we can have a field that can group data together and the
    API can retrieve the proper object. We also need this field in
    order to know the version of the Archetype we are using.""",
    256, None),
   ('string', 'field',
    """the field for the current Archetype that the current row is
    representing in order to provide data bindings (constraints, data
    magnitude etc.) and the proper data type (it's quite easy to convert
    ADL types to Omero Table types). This field will contain the attribute
    code inside the ADL model (like the "at0005" field of the Blood Pressure
    archetype); everything else we need to make this field understandable by
    a human user can be found in the ontology section of the archetype (a name
    in a human language, an explanation about what the field means).""",
    64, None),
   ('string', 'type', "this record type, one of str, long, float, bool",
    10, None),
   ('string', 'svalue', "this record string value",   256, None),
   ('bool',   'bvalue', "this record boolean value",       None),
   ('long',   'lvalue', "this record long value",          None),
   ('double', 'dvalue', "this record double value",        None),
   ]


  # FIXME this should go somewhere central...
  FIELD_TYPE_ENCODING_TABLE = {'int'  : ('long',   'lvalue', 0),
                               'long' : ('long',   'lvalue', 0),
                               'float' : ('float', 'dvalue', 0.0),
                               'str'  :  ('str',   'svalue', None),
                               'bool'  : ('bool',   'bvalue', False)}
  #----------------------------------------------------------------------

  @classmethod
  def encode_field_value(klass, row):
    for k,v in EAVAdapter.FIELD_TYPE_ENCODING_TABLE.iteritems():
      row[v[1]] = v[2]
    value = row['value']
    conv = EAVAdapter.FIELD_TYPE_ENCODING_TABLE[type(value).__name__]
    row['type'] = conv[0]
    # FIXME do we need to upgrade int to long?
    row[conv[1]] = value


  @classmethod
  def decode_field_value(klass, ftype, svalue, bvalue, lvalue, dvalue):
    if ftype == 'str':
      return svalue
    elif ftype == 'long':
      return long(lvalue)
    elif ftype == 'float':
      return float(fvalue)
    elif ftype == 'bool':
      return bool(bvalue)

  def __init__(self, kb):
    self.kb = kb

  def create_ehr_table(self):
    self.kb.create_table(self.EAV_EHR_TABLE, self.EAV_STORAGE_COLS)

  def add_eav_record_row(self, row):
    self.encode_field_value(row)
    self.kb.add_table_row(self.EAV_EHR_TABLE, row)


  def get_eav_record_rows(self, selector, batch_size=50000):
    return  self.kb.get_table_rows(self.EAV_EHR_TABLE, selector,
                                   batch_size)