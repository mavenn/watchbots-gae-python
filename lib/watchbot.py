#!/usr/bin/env python
#

"""Watchbot API

Enables an application to write watchbots for the Mavenn system.

To create a Mavenn watchbot, inherit from the Watchbot class and implement
your bot's functionality.
"""

import logging
import os

import wsgiref.handlers

from google.appengine.ext import webapp
from google.appengine.api import memcache
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from google.appengine.ext.db import djangoforms
from django.template import TemplateDoesNotExist


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
    path = os.path.join(directory, os.path.join('../', 'templates', template_name))
      
    try:
      self.response.out.write(template.render(path, values, debug=True))
    except TemplateDoesNotExist, e:
      self.response.headers["Content-Type"] = "text/html; charset=utf-8"
      self.response.set_status(404)
      self.response.out.write(template.render(os.path.join('../', 'templates', '404.html'), values, debug=True))

  def error(self, status_code):
    webapp.RequestHandler.error(self, status_code)
    if status_code == 404:
      self.generate('404.html')


class Watchbot(BaseHandler):
  """Abstract base class for watchbot implementations."""

  def get(self, action='', format=''):
    """Handle the HTTP GET operations"""
    if action is None or action == '':
      self.list()
    elif action == 'new':
      self.new()
    elif action == 'cron':
      self.cron()
    else:
      # The action is the stream_id
      self.render(action, format)

  def post(self, stream_id='', format=''):
    """Handle the HTTP POST operations"""
    logging.debug("in watchbot post")
    logging.debug(stream_id)
    logging.debug(self.request.POST)

    if stream_id is None or stream_id == '':
      self.create()
    elif stream_id == 'cron':
      self.cron()
    else:
      method = self.request.POST.get("_method")
      if method == 'PUT' or method == 'UPDATE':
        self.update(stream_id)
      elif method == 'DELETE':
        self.remove(stream_id)

  def delete(self, stream_id='', format=''):
    """Handle the HTTP DELETE operation"""
    logging.debug("in watchbot delete")
    logging.debug(stream_id)
    #self.remove(stream_id)
    self.response.set_status(501)
  
  def put(self, stream_id='', format=''):
    """Handle the HTTP PUT operation"""
    logging.debug("in watchbot put")
    logging.debug(stream_id)
    logging.debug(self.request.body)
    #self.update(stream_id)
    self.response.set_status(501)

  def list(self):
    """List the streams created for this bot"""
    return

  def new(self):
    """Display new bot form"""
    return

  def create(self):
    """Override this to create new instance of bot"""
    return

  def render(self, stream_id, format):
    """Render bot's stream, the base class handles common routing.  Override only if you want to handle your own routing.  Otherwise, just override render_html and render_json."""  
    stream = self.get_stream(stream_id)
    if format is None or format == '.html':
      self.render_html(stream)
    elif format == ".json":
      self.render_json(stream)
    else:
      self.error(404)
    return

  def render_html(self, stream):
    """Override this to output the html version of the stream"""
    return
  
  def render_json(self, stream):
    """Override this to output the json version of the stream"""  
    return

  def update(self, stream_id):
    """Override this to handle stream updates"""  
    webapp.RequestHandler.error(self, 501)
    self.response.headers['Content-Type'] = "application/json"
    self.response.out.write('{"status": "not supported"}')
    return
    
  def remove(self, stream_id):
    """Override this to handle stream deletes"""  
    self.response.headers['Content-Type'] = "application/json"
    stream = self.get_stream(stream_id)
    if stream is None:
      webapp.RequestHandler.error(self, 404)
      self.response.out.write('{"status": "failed", "message": "stream not found"}')
    else:
      self.response.out.write('{"status": "success", "message": "stream deleted"}')
    return

  def cron(self):
    """Override this to handle the cron task"""
    return

  def get_stream(self, stream_id):
    """Override this to retrieve an individual stream from the datastore."""  
    return None
  
