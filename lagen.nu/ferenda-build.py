#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
# use when developing the ferenda source code
# import os
# sys.path.append(os.path.normpath(os.getcwd() + os.sep + os.pardir))

from ferenda import manager
manager.run(sys.argv[1:])


