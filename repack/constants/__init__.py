# Copyright (c) 2017-2019 Patricio Cubillos and contributors.
# repack is open-source software under the MIT license (see LICENSE).

import sys, os

from .consts import __all__
from .consts import *

# Clean up top-level namespace--delete everything that isn't in __all__
# or is a magic attribute, and that isn't a submodule of this package
for varname in dir():
    if not ((varname.startswith('__') and varname.endswith('__')) or
            varname in __all__ ):
        del locals()[varname]
del(varname)
