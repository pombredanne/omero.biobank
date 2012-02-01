
"""
Biobank: large scale biomedical computation on OMERO.

Biobank is a framework built upon OMERO that provides compact and
efficient ways to handle the computational aspects of large scale
biomedical studies.
"""

import os, datetime
from distutils.core import setup
from distutils.errors import DistutilsSetupError
from distutils.command.build_py import build_py as du_build_py
from distutils.command.sdist import sdist as du_sdist


CURRENT_YEAR = datetime.datetime.now().year
DESCRIPTION, LONG_DESCRIPTION = __doc__.split("\n", 1)
LONG_DESCRIPTION = LONG_DESCRIPTION.strip()
URL = "http://biobank.sourceforge.net"
# DOWNLOAD_URL = ""
LICENSE = 'GPL'
CLASSIFIERS = [
  "Programming Language :: Python",
  "License :: OSI Approved :: GNU General Public License (GPL)",
  "Operating System :: POSIX :: Linux",
  "Topic :: Scientific/Engineering :: Bio-Informatics",
  "Intended Audience :: Science/Research",
  ]
PLATFORMS = ["Linux"]
try:
  with open("NAME") as f:
    NAME = f.read().strip()
  with open("VERSION") as f:
    VERSION = f.read().strip()
except IOError:
  raise DistutilsSetupError("failed to read name/version info")
AUTHOR_INFO = [
  ("Gianmauro Cuccuru", "gianmauro.cuccuru@crs4.it"),
  ("Simone Leo", "simone.leo@crs4.it"),
  ("Luca Lianas", "luca.lianas@crs4.it"),
  ("Gianluigi Zanetti", "gianluigi.zanetti@crs4.it"),
  ]
MAINTAINER_INFO = [
  ("Simone Leo", "simone.leo@crs4.it"),
  ("Luca Lianas", "luca.lianas@crs4.it"),
  ]
AUTHOR = ", ".join(t[0] for t in AUTHOR_INFO)
AUTHOR_EMAIL = ", ".join("<%s>" % t[1] for t in AUTHOR_INFO)
MAINTAINER = ", ".join(t[0] for t in MAINTAINER_INFO)
MAINTAINER_EMAIL = ", ".join("<%s>" % t[1] for t in MAINTAINER_INFO)


def mtime(fn):
  return os.stat(fn).st_mtime


def up_to_date(dest, src):
  return os.path.exists(dest) and mtime(src) <= mtime(dest)


def write_authors(filename="AUTHORS"):
  if up_to_date(filename, __file__):
    return
  with open(filename, "w") as f:
    f.write("%s is developed by:\n" % NAME)
    for name, email in AUTHOR_INFO:
      f.write(" * %s <%s>\n" % (name, email))
    f.write("and maintained by:\n")
    for name, email in MAINTAINER_INFO:
      f.write(" * %s <%s>\n" % (name, email))


def write_readme(filename="README"):
  if up_to_date(filename, __file__):
    return
  with open(filename, "w") as f:
    f.write("%s\n" % DESCRIPTION)
    f.write("%s\n\n" % ("=" * len(DESCRIPTION)))
    f.write("Copyright %d CRS4. Docs are in docs/html.\n" % CURRENT_YEAR)


def write_version(filename="bl/vl/version.py"):
  if up_to_date(filename, "VERSION"):
    return
  with open(filename, "w") as f:
    f.write("# GENERATED BY setup.py\n")
    f.write("version='%s'\n" % VERSION)


class build_py(du_build_py):
  def run(self):
    write_version()
    write_readme()
    du_build_py.run(self)


class sdist(du_sdist):
  def run(self):
    write_authors()
    du_sdist.run(self)


setup(
  name=NAME,
  description=DESCRIPTION,
  long_description=LONG_DESCRIPTION,
  url=URL,
  ## download_url=DOWNLOAD_URL,
  license=LICENSE,
  classifiers=CLASSIFIERS,
  author=AUTHOR,
  author_email=AUTHOR_EMAIL,
  maintainer=MAINTAINER,
  maintainer_email=MAINTAINER_EMAIL,
  platforms=PLATFORMS,
  version=VERSION,
  packages=[
    'bl',
    'bl.vl',
    'bl.vl.utils',
    'bl.vl.kb',
    'bl.vl.kb.drivers',
    'bl.vl.kb.drivers.omero',
    'bl.vl.individual',
    'bl.vl.genotype',
    'bl.vl.app',
    'bl.vl.app.importer',
    'bl.vl.app.kb_query',
    'bl.vl.app.snp_reannotator',
    ],
  cmdclass={"sdist": sdist, "build_py": build_py},
  )
