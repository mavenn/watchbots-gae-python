
from __future__ import with_statement

import functools
import os
import sys
from fabric.api import *
import datetime
import re

#Some environment information to customize
APPENGINE_PATH = "/opt/google/google_appengine"
#APPENGINE_PATH = "/usr/local/bin" #mac

APPENGINE_DEV_APPSERVER = "%s/dev_appserver.py" % APPENGINE_PATH
APPENGINE_APP_CFG = "%s/appcfg.py" % APPENGINE_PATH
PYTHON = "/usr/bin/python2.5"

#default values
env.gae_application = "feedstreams-stage"
env.gae_src = "./"
env.config_file_to_swap = "config.stage.py"

def hello():
    print("Hello world!")

def test():
    """Run the test suite."""
    local("python ./tests/testrunner.py %s ./tests/" % APPENGINE_PATH)
    
def staging():
    """Sets the deployment target to staging."""
    env.config_file_to_swap = "config.stage.py"
    env.gae_application = "feedstreams-stage"
    pass

def production():
    """Sets the deployment target to production."""
    env.config_file_to_swap = "config.prod.py"
    env.gae_application = "feedstreams"
    
def version(version):
    env.version = version

def run():
    local("cp config.dev.py config.py")
    local("%s %s --port 8080  --use_sqlite %s" % (PYTHON, APPENGINE_DEV_APPSERVER, env.gae_src), capture=False)

def deploy(tag=None):
    prepare_deploy(tag)
    local('%s %s -A %s update %s' % (PYTHON, APPENGINE_APP_CFG, env.gae_application, env.gae_src), capture=False)
    end_deploy()

def prepare_deploy(tag=None):
    local("cp %s config.py" % (env.config_file_to_swap))

def end_deploy():
    """Clean up after deployment"""
    local("git checkout config.py")
