import unittest
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext import testbed


def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.setup_env(app_id=application-id)
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()

def tearDown(self):
    self.testbed.deactivate()