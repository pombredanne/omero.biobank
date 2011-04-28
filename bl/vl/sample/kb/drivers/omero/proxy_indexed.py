"""

ProxyIndexed
============

The goal of this wrapper class is to speed-up object searches and the traversal of the dependencies tree.


save(obj):


  if isinstance(obj, Action):
      if hasattr(obj, target):
         (do not write it twice...)
         write record  A_VID, A_ID, T_VID, T_TABLE_NAME, T_ID

  if isinstance(obj, Result):

      ar =  action record for obj.action.id
      if ar:
         tr = fetch target record for T_VID
         write record O_VID, O_ID, O_TABLE_NAME, O_KLASS, O_MODULE, tr.root_vid
      else:
         write record O_VID, O_ID, O_TABLE_NAME, O_KLASS, O_MODULE, O_VID

FIXME: Current implementation does not handle object deletion.
"""

from proxy_core import ProxyCore
from action import Action

import bl.vl.utils     as vlu
import numpy           as np

import logging
import time

logger = logging.getLogger('proxy_indexed')

counter = 0
def debug_boundary(f):
  def debug_boundary_wrapper(*args, **kv):
    global counter
    now = time.time()
    counter += 1
    logger.debug('%s[%d] in' % (f.__name__, counter))
    res = f(*args, **kv)
    logger.debug('%s[%d] out (%f)' % (f.__name__, counter,
                                      time.time() - now))
    counter -= 1
    return res
  return debug_boundary_wrapper


class ProxyIndexed(ProxyCore):

  ACTION_TABLE='vl_action_table_v4.h5'
  ACTION_RESULT_CLASS_MAX_NAME_LEN = 256
  ACTION_TABLE_COLUMNS =  [('string', 'a_vid',  'Action object VID',        len(vlu.make_vid()), None),
                           ('long',   'a_id',   'Action object ID',         None),
                           ('string', 't_type', 'Target Omero table name', ACTION_RESULT_CLASS_MAX_NAME_LEN, None),
                           ('string', 't_vid',  'Target  VID',             len(vlu.make_vid()), None),
                           ('long',   't_id',   'Target object ID',  None)]
  #--
  TARGET_TABLE='vl_target_table_v4.h5'
  TARGET_RESULT_CLASS_MAX_NAME_LEN = 256
  TARGET_TABLE_COLUMNS =  [('string', 't_type', 'Target Omero table name', TARGET_RESULT_CLASS_MAX_NAME_LEN, None),
                           ('string', 't_vl_class', 'Virgil class name', TARGET_RESULT_CLASS_MAX_NAME_LEN, None),
                           ('string', 't_vl_module', 'Virgil class module', TARGET_RESULT_CLASS_MAX_NAME_LEN, None),
                           ('string', 't_vid',  'Target object VID',        len(vlu.make_vid()), None),
                           ('long',   't_id',   'Target object ID',         None),
                           ('string', 'a_vid',  'Action object VID',        len(vlu.make_vid()), None),
                           ('string', 'r_vid',  'Root object VID',        len(vlu.make_vid()), None),
                           ('string', 'r_type', 'Root object table name', ACTION_RESULT_CLASS_MAX_NAME_LEN, None),
                           ('long',   'r_id',   'Root ID',  None)]
  ROOT_VID = 'VROOT'

  INDEXED_TARGET_TYPES = []

  def __init__(self, host, user, passwd, session_keep_tokens=1):
    super(ProxyIndexed, self).__init__(host, user, passwd, session_keep_tokens)
    self.create_if_missing(self.ACTION_TABLE, self.ACTION_TABLE_COLUMNS)
    self.create_if_missing(self.TARGET_TABLE, self.TARGET_TABLE_COLUMNS)

  #---------------------------------------------------------------------------------------------
  @debug_boundary
  def create_if_missing(self, table_name, fields):
    if not self.table_exists(table_name):
      self.create_table(table_name, fields)
      # FIXME we need to do this because otherwise a table.getNumberOfRows() in get_table_rows will fail.
      #       this appears to be an upstream bug in the omero table support.
      row = dict([(t[1], None if t[0] == 'string' else 0) for t in fields])
      self.add_table_row(table_name, row)

  @debug_boundary
  def _fetch_object_if_needed(self, obj):
    if not obj.loaded:
      query = 'select a from %s a where a.id = :a_id' % obj.get_ome_table()
      pars = self.ome_query_params({'a_id' : obj.ome_obj.id})
      ome_obj = self.ome_operation("getQueryService", "findByQuery", query, pars)
      if not ome_obj:
        logger.error('Could not fetch %s' % obj.ome_obj)
        assert False
      return obj.__class__(ome_obj)
    else:
      return obj

  @debug_boundary
  def save(self, obj):
    logger.debug('processing %s with vid: %s' % (obj.get_ome_table(), obj.id))
    obj = super(ProxyIndexed, self).save(obj)
    if isinstance(obj, Action) and hasattr(obj, 'target'):
      self.__record_action(obj)
    elif filter(lambda x: isinstance(obj, x), self.INDEXED_TARGET_TYPES):
      self.__record_target(obj)
    else:
      logger.debug('no recording of %s with vid: %s' % (obj.get_ome_table(), obj.id))
    return obj

  @debug_boundary
  def delete(self, obj):
    logger.debug('processing %s with vid: %s' % (obj.get_ome_table(), obj.id))
    try:
      if isinstance(obj, Action) and hasattr(obj, 'target'):
        self.__delete_action(obj)
      elif filter(lambda x: isinstance(obj, x), self.INDEXED_TARGET_TYPES):
        self.__delete_target(obj)
    finally:
      obj = super(ProxyIndexed, self).delete(obj)



  @debug_boundary
  def __record_action(self, obj):
    logger.debug('\tprocessing %s with vid: %s' % (obj.get_ome_table(), obj.id))
    target = self._fetch_object_if_needed(obj.target)
    logger.debug('\t\tfetched target %s with vid: %s' % (target.get_ome_table(), target.id))
    #-
    a_vid = obj.id
    if self.get_table_rows(self.ACTION_TABLE, selector='(a_vid == "%s")' % a_vid):
      logger.debug('\t\t %s with vid: %s already registered' % (obj.get_ome_table(), obj.id))
      return
    row = {'a_vid' : a_vid, 'a_id' : obj.omero_id,
           't_vid' : target.id, 't_type' : target.get_ome_table(),
           't_id' : target.omero_id}
    logger.debug('\tsaving in ACTION_TABLE %s' % row)
    self.add_table_row(self.ACTION_TABLE, row)

  @debug_boundary
  def __delete_action(self, obj):
    logger.debug('\tprocessing %s with vid: %s' % (obj.get_ome_table(), obj.id))
    a_vid = obj.id
    row = {'a_vid' : None, 'a_id' : 0, 't_vid' : None, 't_type' : None, 't_id' : 0}
    self.update_table_row(self.ACTION_TABLE, '(a_vid == "%s")' % a_vid, row)

  @debug_boundary
  def __record_target(self, obj):
    logger.debug('\tprocessing %s with vid: %s' % (obj.get_ome_table(), obj.id))
    t_vid = obj.id
    if self.get_table_rows(self.TARGET_TABLE, selector='(t_vid == "%s")' % t_vid):
      logger.debug('\t\t %s with vid: %s already registered' % (obj.get_ome_table(), obj.id))
      return
    #-
    action = self._fetch_object_if_needed(obj.action)
    logger.debug('\t\tfetched %s with vid: %s' % (action.get_ome_table(), action.id))
    a_vid = action.id
    a_row = self.get_table_rows(self.ACTION_TABLE, selector='(a_vid == "%s")' % a_vid)
    logger.debug('\t\taction table row for  %s: %s' % (a_vid, a_row))
    #-
    row = {'t_type' : obj.get_ome_table(),
           't_vl_class' : obj.__class__.__name__, 't_vl_module' : obj.__module__,
           't_vid' : obj.id, 't_id'  : obj.omero_id,
           'r_vid' : obj.id, 'r_type' : obj.get_ome_table(), 'r_id' : obj.omero_id,
           'a_vid' : a_vid}
    if a_row:
      a_row = a_row[0]
      selector = '(t_vid == "%s")' % a_row['t_vid']
      logger.debug('__record_target selector: %s' % selector)
      t_row = self.get_table_rows(self.TARGET_TABLE, selector=selector)
      logger.debug('\t\ttarget table for selection %s returns: %s' % (selector, t_row))
      assert len(t_row) == 1
      t_row = t_row[0]
      row['r_vid'] = t_row['r_vid']
      row['r_type']= t_row['r_type']
      row['r_id']  = int(t_row['r_id']) # FIXME from numpy conversion
    logger.debug('\tsaving in TARGET_TABLE %s' % row)
    self.add_table_row(self.TARGET_TABLE, row)


  @debug_boundary
  def __delete_target(self, obj):
    logger.debug('\tprocessing %s with vid: %s' % (obj.get_ome_table(), obj.id))
    t_vid = obj.id
    row = {'t_type' : None, 't_vl_class' : None, 't_vl_module' : None, 't_vid' : None,
           't_id'  : 0, 'r_vid' : None, 'r_type' : None, 'r_id' : 0, 'a_vid' : None}
    self.update_table_row(self.TARGET_TABLE, '(t_vid == "%s")' % t_vid, row)

  @debug_boundary
  def __extract_object(self, row):
    t_id   = int(row['t_id'])
    t_type = str(row['t_type'])
    mod   = str(row['t_vl_module'])
    klass = str(row['t_vl_class'])
    ome_obj = self.ome_operation("getQueryService", "get", t_type, t_id)
    _tmp = __import__(mod, globals(), locals(), [klass], -1)
    obj = getattr(_tmp, klass)(ome_obj)
    return obj

  @debug_boundary
  def get_root(self, object):
    logger.debug('get_root on %s' % object.ome_obj)
    selector = '(t_id==%d)&(t_type=="%s")' % (object.omero_id, object.get_ome_table())
    logger.debug('get_root selector: %s' % selector)
    o_rows = self.get_table_rows(self.TARGET_TABLE, selector)
    logger.debug('get_root object record[%d]: %s' % (len(o_rows), o_rows))
    assert len(o_rows) == 1
    o_row = o_rows[0]
    if o_row['r_vid'] == o_row['t_vid']:
      return object
    selector = '(t_vid=="%s")' % o_row['r_vid']
    logger.debug('get_root selector: %s' % selector)
    r_rows = self.get_table_rows(self.TARGET_TABLE, selector)
    logger.debug('get_root object record[%d]: %s' % (len(r_rows), r_rows))
    assert len(r_rows) == 1
    r_row = r_rows[0]
    return self.__extract_object(r_row)

  @debug_boundary
  def get_descendants(self, obj, klass=None):
    """
    FIMXE. This function will work only if obj == get_root(obj)
    """
    logger.debug('get_descendants on %s' % obj.ome_obj)
    o_id, o_type = obj.omero_id, obj.get_ome_table()
    select = '(r_id==%d)&(r_type=="%s")' % (o_id, o_type)
    logger.debug('get_descendants select: %s' % select)
    o_rows = self.get_table_rows(self.TARGET_TABLE, select)
    logger.debug('get_descendants object record[%d]: %s' % (len(o_rows), o_rows))
    if len(o_rows) == 0:
      return None
    f_rows = [self.__extract_object(r) for r in o_rows
              if not (r['t_id'] == o_id and r['t_type'] == o_type)
              and ((not klass) or r['t_type'] == klass.get_ome_table())]
    logger.debug('get_descendants objects filtered[%d]: %s' % (len(f_rows), f_rows))
    logger.debug('get_descendants objects filtered[%d]: %s' % (len(f_rows),
                                                               [x.ome_obj for x in f_rows]))
    return f_rows

  def get_actions_tree(self, vid):
    pass
  #----------------------------------------------------------------------------------------------


