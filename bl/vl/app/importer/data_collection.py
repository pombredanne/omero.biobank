"""
Import of Data Collection
=========================

Will read in a tsv file with the following columns::

  study    label data_sample
  BSTUDY   dc-01 V0390290
  BSTUDY   dc-01 V0390291
  BSTUDY   dc-02 V0390292
  BSTUDY   dc-02 V390293
  ....

This will create new DataCollection(s), whose label is defined by the
label column, and link to it, using DataCollectionItem objects,
the DataSample object identified by data_sample (a vid).

Record that point to an unknown (data_sample) will abort the
data collection loading. Previously seen collections will be noisily
ignored too. No, it is not legal to use the importer to add items to a
previously known collection.
"""

from core import Core, BadRecord

from version import version

import csv, json, time

import itertools as it

class Recorder(Core):
  def __init__(self, study_label=None,
               host=None, user=None, passwd=None, keep_tokens=1,
               batch_size=1000, operator='Alfred E. Neumann',
               logger=None, action_setup_conf=None):
    super(Recorder, self).__init__(host, user, passwd, keep_tokens=keep_tokens,
                                   study_label=study_label, logger=logger)
    self.batch_size = batch_size
    self.operator = operator
    self.action_setup_conf = action_setup_conf
    self.preloaded_data_samples = {}
    self.preloaded_data_collections = {}

  def record(self, records, otsv):
    def records_by_chunk(batch_size, records):
      offset = 0
      while len(records[offset:]) > 0:
        yield records[offset:offset+batch_size]
        offset += batch_size

    if len(records) == 0:
      self.logger.warn('no records')
      return

    study = self.find_study(records)
    self.data_sample_klass = self.find_data_sample_klass(records)
    self.preload_data_samples()
    self.preload_data_collections()

    def keyfunc(r): return r['label']

    sub_records = []
    records = sorted(records, key=keyfunc)
    for k, g in it.groupby(records, keyfunc):
      sub_records.append(self.do_consistency_checks(k, list(g)))
    records = sum(sub_records, [])
    if len(records) == 0:
      self.logger.warn('no records')
      return

    asetup = self.get_action_setup('importer.data_collection-%f' % time.time(),
                                   json.dumps(self.action_setup_conf))
    device = self.get_device('importer-%s.data_collection' % version,
                             'CRS4', 'IMPORT', version)
    conf = {'setup' : asetup,
            'device': device,
            'actionCategory' : self.kb.ActionCategory.PROCESSING,
            'operator' : self.operator,
            'context'  : study
            }
    action = self.kb.factory.create(self.kb.Action, conf).save()

    records = sorted(records, key=keyfunc)
    for k, g in it.groupby(records, keyfunc):
      dc_conf = {'label' : k, 'action' : action}
      dc = self.kb.factory.create(self.kb.DataCollection, dc_conf).save()
      for i, c in enumerate(records_by_chunk(self.batch_size, list(g))):
        self.logger.info('start processing chunk %s-%d' % (k, i))
        self.process_chunk(otsv, study, dc, c)
        self.logger.info('done processing chunk %s-%d' % (k,i))


  def find_data_sample_klass(self, records):
    return self.find_klass('data_sample_type', records)

  def preload_data_samples(self):
    self.preload_by_type('data_samples', self.data_sample_klass,
                         self.preloaded_data_samples)

  def preload_data_collections(self):
    self.logger.info('start preloading data collections')
    ds = self.kb.get_objects(self.kb.DataCollection)
    for d in ds:
      self.preloaded_data_collections[d.label] = d
    self.logger.info('there are %d DataCollection(s) in the kb'
                     % len(self.preloaded_data_collections))

  def do_consistency_checks(self, k, records):
    self.logger.info('start consistency checks on %s' % k)
    #--
    if k in self.preloaded_data_collections:
      self.logger.error('There is already a collection with label %s'
                        % k)
      return []

    failures = 0
    seen = []
    for r in records:
      if not r['data_sample'] in self.preloaded_data_samples:
        f = 'bad data_sample in %s.'
        self.logger.error( f % r['label'])
        failures += 1
        continue
      if r['data_sample'] in seen:
        f = 'multiple copy of the same data_sample %s in %s.'
        self.logger.error( f % (r['label'], k))
        failures += 1
        continue
      seen.append(r['data_sample'])

    self.logger.info('done consistency checks on %s' % k)

    return [] if failures else records

  def process_chunk(self, otsv, study, dc, chunk):
    items = []
    for r in chunk:
      conf = {'dataSample' : self.preloaded_data_samples[r['data_sample']],
              'dataCollection' : dc
              }
      items.append(self.kb.factory.create(self.kb.DataCollectionItem, conf))
    #--
    self.kb.save_array(items)
    otsv.writerow({'study' : study.label,
                     'label' : dc.label,
                     'type'  : dc.get_ome_table(),
                     'vid'   : dc.id })

def canonize_records(args, records):
  fields = ['study', 'data_sample_type', 'label']
  for f in fields:
    if hasattr(args, f) and getattr(args,f) is not None:
      for r in records:
        r[f] = getattr(args, f)
  # specific hacks
  for r in records:
    if 'data_sample_type' not in r:
      r['data_sample_type'] = 'DataSample'

def make_parser_data_collection(parser):
  parser.add_argument('--study', type=str,
                      help="""default study used as context
                      for the import action.  It will
                      over-ride the study column value.""")
  parser.add_argument('--data_sample-type', type=str,
                      choices=['DataSample'],
                      help="""default data_sample type.  It will
                      over-ride the data_sample_type column value, if any.""")
  parser.add_argument('--label', type=str,
                      help="""default label for the collection.  It will
                      over-ride the label column value, if any.""")

def import_data_collection_implementation(logger, args):

  action_setup_conf = Recorder.find_action_setup_conf(args)

  recorder = Recorder(args.study,
                      host=args.host, user=args.user, passwd=args.passwd,
                      operator=args.operator,
                      action_setup_conf=action_setup_conf,
                      logger=logger)
  #--
  f = csv.DictReader(args.ifile, delimiter='\t')
  logger.info('start processing file %s' % args.ifile.name)
  records = [r for r in f]

  canonize_records(args, records)

  o = csv.DictWriter(args.ofile,
                     fieldnames=['study', 'label', 'type', 'vid'],
                     delimiter='\t')
  o.writeheader()
  recorder.record(records, o)

  logger.info('done processing file %s' % args.ifile.name)


help_doc = """
import a new data collection definition into a virgil system.
"""

def do_register(registration_list):
  registration_list.append(('data_collection', help_doc,
                            make_parser_data_collection,
                            import_data_collection_implementation))

