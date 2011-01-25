#!/usr/bin/env python

"""App Engine data model (schema) ."""

# Python imports
import logging
import email, time, datetime

# AppEngine imports
from google.appengine.ext import db
from django.utils import simplejson


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
  verify_token = db.StringProperty()  # Random verification token
  pshb_verify_token = db.StringProperty()  # Random verification token
  pshb_hub_url = db.LinkProperty() # store and track it, in case the publisher moves its hub
  pshb_is_subscribed = db.BooleanProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  updated = db.DateTimeProperty(auto_now=True)
  
  @classmethod
  def get_by_url(cls, url):
    return cls.all().filter('url =', url).get()


class FeedItem(db.Model):
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
    """Prepare and save the entry"""
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
      feeditem = cls(stream=feed,
                                 id=id,
                                 title=entry['title'],
                                 url=entry['link'],
                                 summary=description,
                                 author=author,
                                 published=published,
                                 updated=updated)
      return feeditem
    return None
