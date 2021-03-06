#!/usr/bin/env python

# Python imports
import os
import base64
import logging
import uuid
from datetime import datetime

# AppEngine imports
import wsgiref.handlers
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from google.appengine.ext.db import djangoforms
from django.template import TemplateDoesNotExist
from django.utils import simplejson

# 3rd party library imports
from lib import feedfinder
from lib import feedparser

# our own imports
from lib.watchbot import Watchbot
from models import FeedStream, FeedItem, FeedPollerConfig
from config import *


class FeedBot(Watchbot):
  """Mavenn Bot for handling RSS and Atom Feeds"""
  
  def list(self):
    """List the streams created for this bot"""
    streams = FeedStream.all().filter('deleted =', False).fetch(100)
    self.generate('streams.html', {"streams": streams, "title": "Feed Streams", "bot_path": "feeds"})

  def new(self):
    """Display new bot form"""
    form = FeedBotForm(instance=None)
    self.generate('stream_form.html', {"form": form, "bot_path": "feeds"})

  def create(self):
    """Create new instance of bot"""
    streamform = FeedBotForm(data=self.request.POST)
    if streamform.is_valid():
      # shortcut to instantiate entity from form
      feed = streamform.save(commit=False)
      
      # Find the best url (i.e. if a non-feed url passed in, find the feed)
      feed_url = self._find_url_for_feed(feed.url)
      if feed_url:
        feed.url = feed_url
        feed.deleted = False
        feed.pshb_is_subscribed = False
        feed.pshb_verify_token = str(uuid.uuid4())
        feed._key_name = "z%s" % feed.stream_id
        feed.put()

        # get an inital fetch of the feed ASAP
        taskqueue.add(url='/feedpoller/tasks/poll', params={"key":str(feed.key())})
        #key().name()
        
        # attempt to subscribe to feed via PubSubHubBub
        #taskqueue.add(url='/subscriber/subscribe', params={"key":str(feed.key())})
        
        self.response.headers['Content-Type'] = "application/json"
        self.response.out.write('{"status": "success", "message": "stream created"}')
        return
    
    logging.warn("feed failed to be created: %s" % self.request.POST.get('url'))  
    webapp.RequestHandler.error(self, 400)
    self.response.headers['Content-Type'] = "application/json"
    self.response.out.write('{"status": "failed", "message": "stream was not created"}')
    return

  def update(self, stream_id):
    """Update the feed properties"""
    logging.debug("in feedbot update")

    self.response.headers['Content-Type'] = "application/json"
    stream = self.get_stream(stream_id)
    if stream is None:
      webapp.RequestHandler.error(self, 404)
      self.response.out.write('{"status": "failed", "message": "stream not found"}')
      return

    # reset stream properties
    #stream.url = self.request.POST.get('url')
    stream.title = self.request.POST.get('title')
    stream.http_status = None
    stream.http_etag = None
    stream.http_last_modified = None
    stream.last_polled = datetime(1900,1,1)
    stream.put()
    self.response.out.write('{"status": "success", "message": "stream updated"}')

  def remove(self, stream_id):
    """Override this to handle stream deletes"""  
    logging.debug("in feedbot remove")

    self.response.headers['Content-Type'] = "application/json"
    stream = self.get_stream(stream_id)
    if stream is None:
      webapp.RequestHandler.error(self, 404)
      self.response.out.write('{"status": "failed", "message": "stream not found"}')
      return

    stream.deleted = True
    stream.put()
    #TODO: unsubscribe from PubSubHubBub
    self.response.out.write('{"status": "success", "message": "stream deleted"}')

  def get_stream(self, stream_id):
    return FeedStream.get_by_key_name("z%s" % stream_id)    

  def render_html(self, stream):
    if stream is None:
      self.error(404)
      return
    
    items = stream.items.order('-updated').fetch(10)
    self.generate('feed.html', {"items": items, "stream": stream})

  def render_json(self, stream):
    self.response.headers['Content-Type'] = "application/json"

    if stream is None:
      webapp.RequestHandler.error(self, 404)
      self.response.out.write('{"status": "failed", "message": "stream not found"}')
      return
    
    output = {"status": "active", "stream_id": stream.stream_id}
    output["activity"] = self._build_activities(stream)
    self.response.out.write(simplejson.dumps(output))
  
  def _build_activities(self, stream):
    activity = []
    for item in stream.items:
      activity.append(item.to_activity())
    return activity

  def cron(self):
    """Wake up the feed poller"""
    is_enabled = FeedPollerConfig.get_instance().is_enabled 
    if is_enabled is None or is_enabled == False:
      logging.debug("feed poller not enabled")
      self.response.out.write("feed poller not enabled")
      return

    is_running = memcache.get("feed_poller_running")
    if is_running is not None and is_running == True:
      logging.debug("feed poller already running")
      self.response.out.write("feed poller already running")
      return

    # Queue the poller    
    if not memcache.set("feed_poller_running", True):
      logging.error("memcache set failed")
    task = taskqueue.Task(url='/feedpoller/tasks/poll', params={}).add(queue_name="feed-poller")

    logging.debug("woke up the feed poller")
    self.response.out.write("woke up the feed poller")

  def _find_url_for_feed(self, url):
    """Validate that the URl is a real feed, or try to find the feed if not"""
    if feedfinder.isFeed(url):
      return url
    feed_url = feedfinder.feed(url)
    if feed_url:
        return feed_url
    return None
    

class FeedBotForm(djangoforms.ModelForm):
  """Class for use with django forms module"""
  class Meta:
    model = FeedStream
    exclude = ['format','http_status','http_last_modified','http_etag','last_polled','deleted','pshb_is_subscribed','verify_token','pshb_hub_url','pshb_verify_token']


def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([
          ('/feeds', FeedBot),
          (r'/feeds/(new)', FeedBot),
          (r'/feeds/(cron)', FeedBot),
          (r'/feeds/([A-Za-z0-9_]+)(\..*)?', FeedBot)],
          debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
