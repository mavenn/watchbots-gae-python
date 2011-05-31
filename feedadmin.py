#!/usr/bin/env python

# Python imports
import os
import base64
import logging
import uuid
from datetime import datetime

# AppEngine imports
import wsgiref.handlers
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from django.template import TemplateDoesNotExist

# our own imports
from models import FeedStream, FeedItem, FeedPollerConfig


class BaseHandler(webapp.RequestHandler):
  """Supplies a common template generation function.

  When you call generate(), we augment the template variables supplied with
  the current user in the 'user' variable and the current webapp request
  in the 'request' variable.
  """
  def generate(self, template_name, template_values={}):
    values = {
    }

    values.update(template_values)
    directory = os.path.dirname(__file__)
    path = os.path.join(directory, os.path.join('templates', template_name))
      
    try:
      self.response.out.write(template.render(path, values, debug=True))
    except TemplateDoesNotExist, e:
      self.response.headers["Content-Type"] = "text/html; charset=utf-8"
      self.response.set_status(404)
      self.response.out.write(template.render(os.path.join('templates', '404.html'), values, debug=True))

  def error(self, status_code):
    webapp.RequestHandler.error(self, status_code)
    if status_code == 404:
      self.generate('404.html')


class ListHandler(BaseHandler):
  def get(self):
    streams = FeedStream.all().order('-created').fetch(100)
    self.generate('admin/list.html', { "streams": streams })


class ViewHandler(BaseHandler):
  def get(self, key):
    stream = FeedStream.get_by_key_name("z%s" % key)    
    items = stream.items.order('-updated').fetch(10)
    self.generate('admin/view.html', { "items": items, "stream": stream })


class DeleteHandler(BaseHandler):
  def get(self, key):
    stream = FeedStream.get_by_key_name("z%s" % key)    
    self.generate('admin/delete.html')

  def post(self, key):
    stream = FeedStream.get_by_key_name("z%s" % key)
    db.delete(stream.items)
    stream.deleted = True
    stream.put()
    self.redirect('/admin/')
    

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([
          (r'/admin/', ListHandler),
          (r'/admin/feed/(.*)/delete', DeleteHandler),
          (r'/admin/feed/(.*)', ViewHandler)],
          debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
