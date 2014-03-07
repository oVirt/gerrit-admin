#!/usr/bin/env python
import re
import os
from os.path import (
    abspath,
    dirname,
    join as pjoin,
    exists as fexists,
)
import logging


logger = logging.getLogger(__name__)


CONF_FILES = [
    pjoin(dirname(abspath(__file__)), '..', 'config'),
    pjoin(os.environ.get('GIT_DIR', ''), 'hooks', 'config'),
]


def unquote(string):
    if re.match(r'^(\'|").*', string):
        return string[1:-1]
    else:
        return string


class Config(dict):
    def __init__(self, files=None):
        files = files or []
        self.files = []
        for fname in files:
            if not fname:
                continue
            if fexists(fname):
                self.read(fname)
            else:
                logger.warn('Unable to read config file %s' % fname)

    def read(self, filename):
        linenum = 0
        for line in open(filename, 'r'):
            if not line.strip() or line.strip().startswith('#'):
                continue
            if '=' not in line:
                logger.warn('Malformed config entry at %s line %d :\n%s'
                            % (filename, linenum, line))
            key, val = map(lambda x: unquote(str.strip(x)),
                           line.split('=', 1))
            self[key] = val
            linenum += 1
        self.files.append(filename)

    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            logger.error('Unable to get config value %s from any of the '
                         'config files [%s]' % (item, ', '.join(self.files)))
            raise


def load_config():
    return Config(CONF_FILES)
