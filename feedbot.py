# Python imports
import os
import base64
import logging
from datetime import datetime, timedelta

# AppEngine imports
import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from google.appengine.ext.db import djangoforms
from google.appengine.api import urlfetch
from google.appengine.api import taskqueue
from django.template import TemplateDoesNotExist
from django.utils import simplejson

# 3rd party library imports
from lib import feedparser

# our own imports
from lib.watchbot import Watchbot
import models
from config import *


class FeedBot(Watchbot):
  """Mavenn Bot for handling RSS and Atom Feeds"""
  
  def list(self):
    """List the streams created for this bot"""
    streams = models.FeedStream.all().fetch(20)
    self.generate('streams.html', {"streams": streams, "title": "Feed Streams", "bot_path": "feeds"})

  def validate(self, url):
    feed = feedparser.parse(stream.url)
    # Check bozo first
    #Content-Type: text/xml; charset=UTF-8
    #<link rel="alternate" type="application/rss+xml" title="RSS" href="http://www.readwriteweb.com/rss.xml" /> 
    
  def new(self):
    """Display new bot form"""
    form = StreamBotForm(instance=None)
    self.generate('stream_form.html', {"form": form, "bot_path": "feeds"})

  def create(self):
    """Create new instance of bot"""
    form = StreamBotForm(data=self.request.POST)
    if form.is_valid():
      entity = form.save(commit=False)
      entity._key_name = "z%s" % entity.stream_id
      entity.put()
      
      # queue cron
      taskqueue.add(url='/feeds/cron', params={})
      
      self.response.headers['Content-Type'] = "application/json"
      self.response.out.write('{"status": "success", "message": "stream created"}')
    else:
      webapp.RequestHandler.error(self, 400)
      self.response.headers['Content-Type'] = "application/json"
      self.response.out.write('{"status": "failed", "message": "stream was not created"}')

  def update(self, stream_id):
    """Update the feed properties"""
    stream = self.get_stream(stream_id)
    url = self.request.POST.get('url')
    
    # reset stream properties
    stream.url = url
    stream.http_status = None
    stream.http_etag = None
    stream.http_last_modified = None
    stream.last_polled = datetime(1900,1,1)
    stream.put()
    
    self.response.headers['Content-Type'] = "application/json"
    self.response.out.write('{"status": "success", "message": "stream updated"}')

  def get_stream(self, stream_id):
    return models.FeedStream.get_by_key_name("z%s" % stream_id)    

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
    """Action to take when cron invokes this bot"""
    stream = models.FeedStream.all().order('last_polled').get()

    max_age = datetime.utcnow() - timedelta(minutes=15)
    if stream.last_polled >= max_age:
        self.response.out.write("not stale enough")
        return

    d = self._parse_feed(stream)

    # process items
    to_put = []
    for entry in d['entries']:
      item = self._process_entry(entry, stream)
      if item is not None:
        to_put.append(item)

    # persist new items
    if len(to_put) > 0:
      db.put(to_put)
      self.update_mavenn_activity(stream.stream_id, to_put)

    # update stream
    if 'status' in d:
      stream.http_status = str(d.status)
      if 'modified' in d:
        stream.http_last_modified = datetime(*d.modified[:6])
      if 'etag' in d:
        stream.http_etag = d.etag
    stream.last_polled = datetime.utcnow()
    stream.put()
    self.response.out.write("stream updated")
    return

  def _parse_feed(self, stream):
    """Helper method to handle conditional HTTP stuff"""
    if stream.http_etag is not None and len(stream.http_etag) > 0 and stream.http_last_modified is not None:
      # give feedparser back what it pulled originally, a time.struct_time object
      return feedparser.parse(stream.url, etag=stream.http_etag, modified=stream.http_last_modified.timetuple())
    if stream.http_etag is not None and len(stream.http_etag) > 0:
      return feedparser.parse(stream.url, etag=stream.http_etag)
    if stream.http_last_modified is not None:
      # give feedparser back what it pulled originally, a time.struct_time object
      return feedparser.parse(stream.url, modified=stream.http_last_modified.timetuple())
    else:
      return feedparser.parse(stream.url)

  def _process_entry(self, entry, stream):
    id = None
    published = None
    updated = None
    author = None
    if 'published' in entry:
      published = datetime(*entry.published_parsed[:6])
    if 'updated' in entry:
      updated = datetime(*entry.updated_parsed[:6])
    if 'id' in entry:
      id = entry['id']
    if 'author' in entry:
      author = entry['author']

    item_exists = stream.items.filter('id =', id).get()
    if item_exists is None:
      feeditem = models.FeedItem(stream=stream,
                                 id=id,
                                 title=entry['title'],
                                 url=entry['link'],
                                 summary=entry['description'],
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
    result = urlfetch.fetch(url, payload=activity, method=urlfetch.POST,headers=headers)
    logging.debug(result.status_code)
    logging.debug(result.headers)
    #logging.debug(result.content)


class StreamBotForm(djangoforms.ModelForm):
  class Meta:
    model = models.FeedStream
    exclude = ['format','http_status','http_last_modified','http_etag','last_polled']


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
