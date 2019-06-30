# Copyright (c) 2017-2019 Patricio Cubillos and contributors.
# repack is open-source software under the MIT license (see LICENSE).

import os
import re
import sys
import setuptools
from setuptools import setup, Extension
from numpy import get_include

topdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(topdir + "/repack")
import VERSION as v

version = '{:d}.{:d}.{:d}'.format(v.repack_VER, v.repack_MIN, v.repack_REV)

srcdir = './repack/utils/'  # C-code source folder

# Get all file from source dir:
files = os.listdir(srcdir)
# Filter the results for just the c files:
files = list(filter(lambda x:     re.search('.+[.]c$',     x), files))
files = list(filter(lambda x: not re.search('[.#].+[.]c$', x), files))

inc = [get_include()]
eca = ['-ffast-math']
ela = []

extensions = []
for cfile in files:
    e = Extension('repack.utils.'+cfile.rstrip('.c'),
                  sources=["{:s}{:s}".format(srcdir, cfile)],
                  include_dirs=inc,
                  extra_compile_args=eca,
                  extra_link_args=ela)
    extensions.append(e)

setup(name         = "repack",
      version      = version,
      author       = "Patricio Cubillos",
      author_email = "patricio.cubillos@oeaw.ac.at",
      url          = "https://github.com/pcubillos/repack",
      packages     = setuptools.find_packages(),
      install_requires = [
                     'numpy>=1.13.3',
                     'scipy>=0.17.1',
                     ],
      license      = "MIT",
      description  = 'Repack line-transition data.',
      include_dirs = inc,
      ext_modules  = extensions)

