"""
Import Marker Alignments
========================

Will read in a tsv file with the following columns::

  marker_vid ref_genome chromosome pos      strand allele copies
  V0909090   hg18       10         82938938 True   A      1
  V0909091   hg18       1          82938999 True   A      2
  V0909092   hg18       1          82938938 True   B      2
  ...

The pos fields is relative to 5': if the marker has been aligned on
the other strand, it is the responsibility of the aligner app to
report the actual distance from 5', while, at the same time,
registering that the SNP has actually been aligned on the other
strand. The chromosome field is an integer field with values in the
[1, 26] range, with 23-26 representing, respectively, the X
chromosome, the Y chromosome, the pseudoautosomal regions (XY) and the
mitochondrial DNA (MT).
"""
import csv, json, time, os

import core
from version import version


MANDATORY_FIELDS = [
  'marker_vid',
  'ref_genome',
  'chromosome',
  'pos',
  'strand',
  'allele',
  'copies',
  ]
STRAND_ENCODINGS = frozenset(['TRUE', '+'])


class Recorder(core.Core):
  
  def __init__(self, study_label, host=None, user=None, passwd=None,
               keep_tokens=1, action_setup_conf=None, logger=None,
               operator='Alfred E. Neumann', ms_label=None):
    super(Recorder, self).__init__(host, user, passwd, keep_tokens=keep_tokens,
                                   study_label=study_label, logger=logger)
    self.action_setup_conf = action_setup_conf
    device_label = ('importer.marker_alignment.SNP-marker-alignment-%s' %
                    version)
    device = self.get_device(label=device_label,
                             maker='CRS4', model='importer', release='0.1')
    asetup = self.get_action_setup(
      'importer.marker_alignment-%f' % time.time(),
      json.dumps(self.action_setup_conf)
      )
    acat = self.kb.ActionCategory.IMPORT
    conf = {
      'setup': asetup,
      'device': device,
      'actionCategory': acat,
      'operator': operator,
      'context': self.default_study,
      }
    self.action = self.kb.factory.create(self.kb.Action, conf)
    #-- FIXME what happens if we do not have alignments to save?
    self.action.save()
    self.mset_vid = self.__get_mset_vid(ms_label)

  def __get_mset_vid(self, ms_label):
    if ms_label is None:
      return None
    mset = self.kb.get_snp_markers_set(ms_label)
    if mset is None:
      self.logger.warn('no marker set labeled %r, setting to None' % ms_label)
      return None
    return mset.id

  def do_consistency_checks(self, records):
    self.logger.info('start consistency checks')
    vids = [r['marker_vid'] for r in records]
    markers = dict((m.id, m) for m in self.kb.get_snp_markers(
      vids=vids, col_names=['vid']
      ))
    accepted = []
    for i, r in enumerate(records):
      reject = 'Rejecting import of record %d: ' % i
      if not r['marker_vid'] in markers:
        f = reject + 'unkown marker_vid value.'
        self.logger.error(f)
        continue
      if self.missing_fields(MANDATORY_FIELDS, r):
        f = reject + 'missing mandatory field.'
        self.logger.error(f)
        continue
      if not 0 < r['chromosome'] < 27:
        f = reject + 'chomosome value out ot the [1:26] range.'
        self.logger.error(f)
        continue
      if not 0 < r['pos']:
        f = reject + 'non positive pos.'
        self.logger.error(f)
        continue
      accepted.append(r)
    return accepted

  def record(self, records):
    records = self.do_consistency_checks(records)
    self.kb.add_snp_alignments(records, op_vid=self.action.id,
                               ms_vid=self.mset_vid)


class RecordCanonizer(core.RecordCanonizer):

  def canonize(self, r):
    super(RecordCanonizer, self).canonize(r)
    r['chromosome'] = int(r['chromosome'])
    r['pos'] = int(r['pos'])
    r['global_pos'] = 10**10 * r['chromosome'] + r['pos']
    r['strand'] = r['strand'].upper() in STRAND_ENCODINGS
    r['copies'] = int(r['copies'])


help_doc = """
import new marker alignments into the KB.
"""


def make_parser(parser):
  parser.add_argument('-S', '--study', metavar="STRING", required=True,
                      help="study label")
  parser.add_argument('--markers-set', metavar="STRING", required=True,
                      help="related markers set")
  parser.add_argument('--ref-genome', metavar="STRING",
                      help="reference genome, e.g., hg19")


def implementation(logger, args):
  fields_to_canonize = ['study', 'ref_genome']
  action_setup_conf = Recorder.find_action_setup_conf(args)
  recorder = Recorder(args.study,
                      host=args.host, user=args.user, passwd=args.passwd,
                      action_setup_conf=action_setup_conf,
                      operator=args.operator, logger=logger, keep_tokens=1,
                      ms_label=args.markers_set)
  f = csv.DictReader(args.ifile, delimiter='\t')
  recorder.logger.info('start processing file %s' % args.ifile.name)
  records = []
  for r in f:
    if r['chromosome'] == 'None':
      logger.warn('%s: chr is None, skipping' % r['marker_vid'])
    else:
      records.append(r)
  args.ifile.close()
  canonizer = RecordCanonizer(fields_to_canonize, args)
  canonizer.canonize_list(records)
  recorder.record(records)
  recorder.logger.info('done processing file %s' % args.ifile.name)


def do_register(registration_list):
  registration_list.append(('marker_alignment', help_doc, make_parser,
                            implementation))
