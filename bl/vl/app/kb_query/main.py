# BEGIN_COPYRIGHT
# END_COPYRIGHT

"""
``kb_query`` is the basic command line tool for extracting information
from the Knowledge Base (KB).
"""

import sys, argparse
from importlib import import_module

import bl.vl.utils.ome_utils as vlu
from bl.vl.utils import LOG_LEVELS, get_logger


SUBMOD_NAMES = [
  "map_vid",
  "global_stats",
  "selector",
  "query",
  "extract_genotypes",
  "build_gstudio_datasheet",
  "plates_data_samples",
  "vessels_by_individual",
  "map_to_collection",
  "flowcell_samplesheet",
  "seq_run_results",
  # "tabular",
  "markers",
  # "ehr",
  ]
SUBMODULES = [import_module("%s.%s" % (__package__, n)) for n in SUBMOD_NAMES]


class App(object):
  
  def __init__(self):
    self.supported_submodules = []
    for m in SUBMODULES:
      m.do_register(self.supported_submodules)

  def make_parser(self):
    parser = argparse.ArgumentParser(description="KB query tool")
    parser.add_argument('--logfile', metavar="FILE",
                        help='log file, defaults to stderr')
    parser.add_argument('--loglevel', metavar="STRING",
                        choices=LOG_LEVELS,
                        help='logging level', default='INFO')
    parser.add_argument('-o', '--ofile', type=argparse.FileType('w'),
                        help='output tsv file', default=sys.stdout)
    parser.add_argument('-H', '--host', metavar="STRING",
                        help='OMERO hostname')
    parser.add_argument('-U', '--user', metavar="STRING",
                        help='OMERO user')
    parser.add_argument('-P', '--passwd', metavar="STRING",
                        help='OMERO password')
    parser.add_argument('--operator', metavar="STRING",
                        help='operator identifier', required=True)
    parser.add_argument('-K', '--keep-tokens', type=int,
                        default=1, help='OMERO tokens for open session')
    subparsers = parser.add_subparsers()
    for k, h, addp, impl in self.supported_submodules:
      subparser = subparsers.add_parser(k, help=h)
      addp(subparser)
      subparser.set_defaults(func=impl)
    self.parser = parser
    return parser

def main(argv=None):
  app = App()
  parser = app.make_parser()
  args = parser.parse_args(argv)
  logger = get_logger("main", level=args.loglevel, filename=args.logfile)
  try:
    host = args.host or vlu.ome_host()
    user = args.user or vlu.ome_user()
    passwd = args.passwd or vlu.ome_passwd()
  except ValueError, ve:
    logger.critical(ve)
    sys.exit(ve)
  args.func(logger, host, user, passwd, args)
