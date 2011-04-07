import os, unittest, time
import itertools as it
from bl.lib.sample.kb import KBError
from bl.lib.genotype.kb.drivers.omero.proxy import Proxy

import vl.lib.utils as vlu

import numpy as np

import logging
logging.basicConfig(level=logging.DEBUG)


OME_HOST = os.getenv("OME_HOST", "localhost")
OME_USER = os.getenv("OME_USER", "root")
OME_PASS = os.getenv("OME_PASS", "romeo")

BATCH_SIZE=1000

class SafeProxy(Proxy):
  SNP_MARKER_DEFINITIONS_TABLE = 'UNIT_TESTING.' + Proxy.SNP_MARKER_DEFINITIONS_TABLE
  SNP_ALIGNMENT_TABLE         = 'UNIT_TESTING.' + Proxy.SNP_ALIGNMENT_TABLE
  SNP_SET_DEF_TABLE           = 'UNIT_TESTING.' + Proxy.SNP_SET_DEF_TABLE
  SNP_SET_TABLE               = 'UNIT_TESTING.' + Proxy.SNP_SET_TABLE

class TestGdos(unittest.TestCase):
  def setUp(self):
    self.proxy = SafeProxy(OME_HOST, OME_USER, OME_PASS)
    self.tearDown()
    self.proxy.create_snp_marker_definitions_table()
    self.proxy.create_snp_markers_set_table()
    self.proxy.create_snp_set_table()

  def tearDown(self):
    for tn in [SafeProxy.SNP_MARKER_DEFINITIONS_TABLE,
               SafeProxy.SNP_ALIGNMENT_TABLE,
               SafeProxy.SNP_SET_DEF_TABLE,
               SafeProxy.SNP_SET_TABLE
               ]:

      self.proxy.delete_table(tn)

  def define_new_genotyping_technology(self):
    N_CALLS = 10
    N_GENOTYPES = 10
    #-- define markers
    source, context  = ['src-%d' % int(time.time()), 'cxt-%d' % int(time.time())]
    op_vid  = vlu.make_vid()
    mds = [{'source' : source,
            'context': context,
            'label':   'foo-%06d' % i,
            'rs_label': 'rs-%06d' % i,
            'mask'    : 'GGATACATTTTATTGC[A/G]CTTGCAGAGTATTTTT'} for i in range(N_CALLS)]
    vids = self.proxy.add_snp_marker_definitions(it.islice(mds, len(mds)), op_vid=op_vid)
    #-- define markers set
    mrks = self.proxy.get_snp_marker_definitions(selector='(op_vid=="%s")' % op_vid)
    set_op_vid  = vlu.make_vid()
    maker   = 'foomatic'
    model   = 'barfoo'
    self.assertEqual(len(mds), len(mrks))
    mds = [{'marker_vid' : m['vid'],
            'marker_indx' : i,
            'allele_flip' : [True, False][np.random.random_integers(0,1)],
            } for i, m in enumerate(mrks)]
    set_vid = self.proxy.add_snp_markers_set(maker, model,op_vid=set_op_vid)
    self.proxy.fill_snp_markers_set(set_vid, it.islice(mds, len(mds)), op_vid=set_op_vid)
    #-- define new genotype repository
    self.proxy.create_gdo_repository(set_vid, len(mds))
    probs = np.zeros((2,N_CALLS), dtype=np.float32)
    confs = np.zeros((N_CALLS,),  dtype=np.float32)
    p_A = 0.3
    results = {}
    for i in range(N_GENOTYPES):
      probs[0,:] = np.random.normal(p_A**2, 0.01*p_A**2, N_CALLS)
      probs[1,:] = np.random.normal((1.-p_A)**2, 0.01*(1.0-p_A)**2, N_CALLS)
      confs[:]   = np.random.normal(0.5, 0.01*0.5, N_CALLS)
      if (i%4) == 0:
        # generate 0-ending probs to test 'short' data strings
        probs[1,N_CALLS-4:] = 0
        confs[N_CALLS-4:] = 0
      op_vid = vlu.make_vid()
      vid = self.proxy.add_gdo(set_vid, probs, confs, op_vid)
      results[vid] = (probs.copy(), confs.copy())

    for k in results.keys():
      r  = self.proxy.get_gdo(set_vid, k)
      self.assertTrue(np.all(np.equal(r['probs'], results[k][0])))
      self.assertTrue(np.all(np.equal(r['confidence'], results[k][1])))

    s = self.proxy.get_gdo_iterator(set_vid, batch_size=4)
    for i, r in enumerate(s):
      k = r['vid']
      self.assertTrue(np.all(np.equal(r['probs'], results[k][0])))
      self.assertTrue(np.all(np.equal(r['confidence'], results[k][1])))
    self.assertEqual(i+1, len(results))

def suite():
  suite = unittest.TestSuite()
  suite.addTest(TestGdos('define_new_genotyping_technology'))
  return suite


if __name__ == '__main__':
  runner = unittest.TextTestRunner(verbosity=2)
  runner.run((suite()))