# Python imports
import os
import base64
import logging
from datetime import datetime, timedelta

# AppEngine imports
import wsgiref.handlers
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
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
import models
from config import *


class FeedPoller(webapp.RequestHandler):
  """Class that encapsulates the feed poller functions"""
  def post(self):
    is_enabled = memcache.get("feed_poller_enabled")
    if is_enabled is None or is_enabled == False:
      logging.info("feed poller not enabled shutting down")
      self.response.out.write("feed poller not enabled shutting down")
      return

    # Get the stalest feed
    feed = models.FeedStream.all().filter('deleted = ', False).order('last_polled').get()

    # Check how stale the stalest feed is, if it's been updated in the
    # last 10 minutes, we should take a break
    max_age = datetime.utcnow() - timedelta(minutes=10)
    if feed.last_polled >= max_age:
      if not memcache.set("feed_poller_running", False):
        logging.error("memcache set failed")
      logging.info("putting feed poller to sleep")
      self.response.out.write("putting feed poller to sleep")
      return

    # go get the feed
    self.update_feed(feed)
    
    # Queue the next feed
    task = taskqueue.Task(url='/feedpoller/tasks/poll', params={}).add(queue_name="feed-poller")
    self.response.out.write("feed updated")

  def update_feed(self, feed):
    """Fetch the feed and process new items"""
    d = self.parse_feed(feed)

    # process items
    to_put = []
    for entry in d['entries']:
      item = self.process_entry(entry, feed)
      if item is not None:
        to_put.append(item)

    # persist new items
    if len(to_put) > 0:
      db.put(to_put)
      self.update_mavenn_activity(feed.stream_id, to_put)

    # update stream
    if 'status' in d:
      logging.info(d.status)
      feed.http_status = str(d.status)
      if 'modified' in d:
        feed.http_last_modified = datetime(*d.modified[:6])
      if 'etag' in d:
        feed.http_etag = d.etag
    feed.last_polled = datetime.utcnow()
    feed.put()
    return

  def parse_feed(self, feed):
    """Helper method to handle conditional HTTP stuff"""
    try:
      logging.info("Requesting Feed for: %s" % feed.url)
      if feed.http_etag is not None and len(feed.http_etag) > 0 and feed.http_last_modified is not None:
        # give feedparser back what it pulled originally, a time.struct_time object
        return feedparser.parse(feed.url, etag=feed.http_etag, modified=feed.http_last_modified.timetuple())
      if feed.http_etag is not None and len(feed.http_etag) > 0:
        return feedparser.parse(feed.url, etag=feed.http_etag)
      if feed.http_last_modified is not None:
        # give feedparser back what it pulled originally, a time.struct_time object
        return feedparser.parse(feed.url, modified=feed.http_last_modified.timetuple())
      else:
        return feedparser.parse(feed.url)
    except UnicodeDecodeError:
        logging.error("Unicode error parsing feed: %s" % feed.url)
        return None

  def process_entry(self, entry, feed):
    id = None
    published = None
    updated = None
    author = None
    description = None
    if 'published' in entry:
      published = datetime(*entry.published_parsed[:6])
    if 'updated' in entry:
      updated = datetime(*entry.updated_parsed[:6])
    if 'id' in entry:
      id = entry['id']
    if 'author' in entry:
      author = entry['author']
    # Per RSS spec, at least one of title or description must be present.
    if 'description' in entry:
      description = entry['description']
    else:
      description = entry['title']

    item_exists = feed.items.filter('id =', id).get()
    if item_exists is None:
      feeditem = models.FeedItem(stream=feed,
                                 id=id,
                                 title=entry['title'],
                                 url=entry['link'],
                                 summary=description,
                                 author=author,
                                 published=published,
                                 updated=updated)
      return feeditem
    return None

  def update_mavenn_activity(self, stream_id, items):
    mavenn_activity_update = {"status": "active", "stream_id": stream_id}
    activities = []
    for item in items:
      activities.append(item.to_activity())
    mavenn_activity_update["activity"] = activities
    activity = simplejson.dumps(mavenn_activity_update)
    
    url = "http://mavenn.com/2010-10-17/streams/%s/activity" % stream_id
    pair = "%s:%s" % (FEEDBOT_MAVENN_API_KEY, FEEDBOT_MAVENN_AUTH_TOKEN)
    token = base64.b64encode(pair)
    headers = {"Content-Type": "application/json", "Authorization": "Basic %s" % token}
    #result = urlfetch.fetch(url, payload=activity, method=urlfetch.POST,headers=headers)
    logging.debug(result.status_code)
    logging.debug(result.headers)
    #logging.debug(result.content)
    return


class FeedPollerSwitch(webapp.RequestHandler):
  """Turn the feed poller on and off"""
  def get(self):
    is_feed_poller_enabled = memcache.get("feed_poller_enabled")
    if is_feed_poller_enabled is None or is_feed_poller_enabled == False:
      if not memcache.set("feed_poller_enabled", True):
        logging.error("Memcache set failed for FeedPollerSwitch")
    else:
      if not memcache.set("feed_poller_enabled", False):
        logging.error("Memcache set failed for FeedPollerSwitch")
    self.response.out.write("enabled %s" % memcache.get("feed_poller_enabled"))
    

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([
          (r'/feedpoller/tasks/poll', FeedPoller),
          (r'/feedpoller/toggle', FeedPollerSwitch)
          ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
