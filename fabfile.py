
from __future__ import with_statement

import functools
import os
import sys
from fabric.api import *
import datetime
import re

#Some environment information to customize
APPENGINE_DEV_APPSERVER = "/opt/google/google_appengine/dev_appserver.py"
APPENGINE_PATH = "/opt/google/google_appengine/"
APPENGINE_APP_CFG = "/opt/google/google_appengine/appcfg.py"
PYTHON = "/usr/bin/python2.5"

#default values
env.version = "staging"
env.gae_email = ""
env.gae_src = "./"

def hello():
    print("Hello world!")

def test():
    """Run the test suite."""
    x = 5
    
def staging():
    """Sets the deployment target to staging."""
    env.version = "staging"
    pass

def production():
    """Sets the deployment target to production."""
    env.version = "feedstreams"
    
def version(version):
    env.version = version

def run():
    local("%s %s --port 8080  --use_sqlite %s" % (PYTHON, APPENGINE_DEV_APPSERVER, env.gae_src), capture=False)

def deploy(tag=None):
    prepare_deploy(tag)
    local('%s %s -A %s --email=%s update %s' % (PYTHON, APPENGINE_APP_CFG, env.version, env.gae_email, env.gae_src), capture=False)
    end_deploy()

def prepare_deploy(tag=None):
    x = 5
