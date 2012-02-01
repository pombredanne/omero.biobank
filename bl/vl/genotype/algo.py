# BEGIN_COPYRIGHT
# END_COPYRIGHT

"""
Genotyping-related algorithms
=============================

This is a collection of simple algorithms used to analyze genotype
data. It is assumed that the latter is provided as an iterator whose
``next`` method returns a ``dict`` with the following fields:

* row_id: the row id of the GDO within its global container

* vid: the VID of the GDO

* probs: a numpy array like ``np.zeros((2,N), dtype=np.float32)``
  where (0,:) (1,:) are, respectively, the prob_A and prob_B arrays

* confs: a numpy array like ``np.zeros((N,), dtype=np.float32)`` with
  the confidence values corresponding to the probs

where ``N`` is the number of SNPs in the data set.
"""

import numpy as np


def project_to_discrete_genotype(probs, threshold=0.2):
  """
  Convert a probabilistic genotype description to the classical
  discrete view. Returns an array of integers, with::

    AA    -> 0
    BB    -> 1
    AB    -> 2
    undef -> 3
  """
  x = np.vstack([probs, 1.0 - probs.sum(axis=0)])
  xt = np.transpose(x)
  idx = np.argsort(xt)
  offsets = np.array(xrange(xt.shape[0]))
  offsets *= idx.shape[1]
  offsets.shape = (offsets.shape[0], 1)
  sels = idx[:, -1]
  xtw = np.take(xt, idx + offsets)
  c = (xtw[:,-2] / (xtw[:,-1] + 1e-6)) < threshold
  res = np.select([c], [idx[:,-1]], default=3)
  return res


def count_homozygotes(it):
  """
  Count the number of AA, BB homozygotes.

  :param it: a stream of GDOs
  :type it: iterator

  :rtype: type(np.zeros((2,N), dtype=np.int32))
  """
  setup_done = False
  for i, x in enumerate(it):
    probs = x['probs']
    if not setup_done:
      counts = np.zeros(probs.shape, dtype=np.float32)
      setup_done = True
    counts += probs
  return (i + 1), np.cast[np.int32](counts)


def maf(it, counts=None):
  """
  Compute Minor Allele Frequencies.

  :param it: a stream of GDOs
  :type it: iterator
  
  :param counts: the result of calling count_homozygotes(it)
  :type counts: type(np.zeros((2,N), dtype=np.int32))

  :rtype: type(np.zeros((2,N), dtype=np.int32)))
  """
  if not counts:
    N, counts = count_homozygotes(it)
  else:
    N, counts = counts
  N_AB = N - counts.sum(axis=0)
  return (2*counts + N_AB)/(2.0*N)


def hwe_probabilites(n_a, n_ab, N):
  n_a = n_a if n_a <= N else 2*N - n_a
  if n_a == 0:
    return (1.0, np.array([1.0,]))
  n_b = 2*N - n_a
  N_ab = np.arange(n_a & 0x01, n_a, 2, dtype=np.float64)
  log_fact = np.log((n_a - N_ab) * (n_b - N_ab) / ((N_ab + 2.0) * (N_ab + 1.0)))
  weight = np.cumsum(log_fact)
  prob = np.exp(weight - weight.max())
  prob /= prob.sum()
  if n_a != n_ab:
    return (prob[N_ab == n_ab], prob)
  else:
    return (0, np.hstack((prob, 0)))


def hwe_scalar(n_a, n_ab, N):
  p, probs = hwe_probabilites(n_a, n_ab, N)
  return probs[probs <= p].sum()


hwe_vector = np.vectorize(hwe_scalar, [np.float32])


def hwe(it, counts=None):
  """
  Implement Hardy-Weinberg exact calculation using the method described in
  Wigginton et al., Am.J.Hum.Genet.vol.76-pp.887.

  It returns an array with the probabilities that the distribution of
  alleles seen for each marker is compatible with the Hardy-Weinberg
  Equilibrium (HWE).

  .. math::

     P_{HWE} = \sum_{n^*_{AB}} I[P(N_{AB}=n_{AB}|N,n_A) \geq P(N_{AB}=n^*_{AB}|N,n_A)] \\times P(N_{AB}=n^*_{AB}|N,n_A)

  Where :math:`I[x]` is an indicator function that is equal to 1 when
  :math:`x` is true and equal to 0 otherwise.

  That is, we are computing the probability that the real value of the
  HWE will be below the one that would be predicted from :math:`N`
  (total number of diploid individuals) and :math:`n_A`, the measured
  count of the allele A.

  :param it: a stream of GDOs
  :type it: iterator
  
  :param counts: the result of calling count_homozygotes(it)
  :type counts: type(np.zeros((2,N), dtype=np.int32))

  :rtype: type(np.zeros((N,), dtype=np.float32))
  """
  if not counts:
    N, counts = count_homozygotes(it)
  else:
    N, counts = counts
  N_AB = N - counts.sum(axis=0)
  N_x = N_AB + 2*counts
  low_freq = N_x.min(axis=0)
  return hwe_vector(low_freq, N_AB, N)


def find_shared_support(kb, gdos):
  """
  Find the set of markers that are shared by a group of GDOs.

  :param kb: the knowledge base
  :type  kb: KnowledgeBase

  :param gdos: a stream of GDOs
  :type gdos: iterator

  :return: (marker_ids, index_arrays) tuple. marker_ids is the list of
    shared markers vids, while index_array is a list that contains, for
    each GDO, an np.array that indexes the selected GDO support markers.
  """
  set_vids = [g['set_vid']  for g in gdos]
  I = None
  set_rows = {}
  for v in set(set_vids):
    r = kb.get_snp_set_table_rows("(vid=='%s')"%v)
    set_rows[v] = r
    if I is None:
      I = r[1]
    else:
      I = np.intersect1d(I, r[1])
  selected = {}
  for k in set_rows.keys():
    r = set_rows[k]
    mrk_to_idx = dict(it.izip(r[1], r[2]))
    selected[k] = np.array([mrk_to_idx[m] for m in I], dtype=np.int32)
  return (I, [selected[v] for v in set_vids])
