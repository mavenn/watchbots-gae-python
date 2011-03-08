#!/usr/bin/env python

"""App Engine data model (schema) ."""

# Python imports
import datetime
import email
import hashlib
import logging
import random
import time

# AppEngine imports
from google.appengine.ext import db
from django.utils import simplejson

from lib import feedparser


class FeedStream(db.Model):
  stream_id = db.StringProperty(required=True)
  title = db.StringProperty(required=True)
  url = db.LinkProperty()
  format = db.StringProperty()
  http_status = db.StringProperty()
  http_last_modified = db.DateTimeProperty()
  http_etag = db.StringProperty()
  last_polled = db.DateTimeProperty(default=datetime.datetime(1900,1,1))
  deleted = db.BooleanProperty()
  pshb_verify_token = db.StringProperty()  # Random verification token
  pshb_hub_url = db.LinkProperty() # store and track it, in case the publisher moves its hub
  pshb_is_subscribed = db.BooleanProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  updated = db.DateTimeProperty(auto_now=True)
  
  @classmethod
  def get_by_url(cls, url):
    return cls.all().filter('url =', url).get()


class FeedItem(db.Model):
  """An invidual story or item from a feed.
  Key name will be a hash of the feed source and item ID.
  """
  stream = db.ReferenceProperty(FeedStream, collection_name='items')
  id = db.StringProperty()
  title = db.StringProperty()
  author = db.StringProperty()
  url = db.LinkProperty()
  summary = db.TextProperty()
  content = db.TextProperty()
  published = db.DateTimeProperty()
  updated = db.DateTimeProperty()
  mavenn_posted_at = db.DateTimeProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  
  def to_activity(self):
    activity_time = self.published
    if activity_time is None:
      activity_time = self.updated
    activity = {
      "action": {"type": "feeditem",
                 "summary": self.summary,
                 "time": activity_time.strftime("%a, %d %b %Y %H:%M:%S +0000"),
                 "uid": str(self.key()),
                 "url": self.url,
                 "meta": {},
                 "title": self.title},
      "object": {"url": self.url},
      "actor": {"person": self.author}
      }
    return activity

  @classmethod
  def process_entry(cls, entry, feed):
    """Prepare the feed entry, converting it to our FeedItem model"""
    entry_id = None
    content = None
    published = None
    updated = None
    link = entry.get('link', '')
    title = entry.get('title', '')
    author = entry.get('author', '')

    if hasattr(entry, 'content'):
      # This is Atom.
      entry_id = entry.id
      content = entry.content[0].value
    else:
      # Per RSS spec, at least one of title or description must be present.
      content = (entry.get('description', '') or title)
      entry_id = (entry.get('id', '') or link or title)

    if hasattr(entry, 'published'):
      published = datetime.datetime(*entry.published_parsed[:6])
    if hasattr(entry, 'updated'):
      updated = datetime.datetime(*entry.updated_parsed[:6])
      
    entry_key_name = 'z' + hashlib.sha1(link + '\n' + entry_id + '\n' + feed.stream_id).hexdigest()
    feeditem = cls(key_name=entry_key_name,
      stream=feed,
      id=entry_id,
      title=unicode(title),
      url=link,
      summary=unicode(content),
      author=unicode(author),
      published=published,
      updated=updated)
    return feeditem
