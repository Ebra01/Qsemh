#!usr/bin/env python3.7.9
import imp
import os
import sys

INTERP = "/usr/local/bin/python3.7"
if sys.executable != INTERP: os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, os.path.dirname(__file__))

wsgi = imp.load_source('wsgi', 'wsgi.py')
application = wsgi.app
