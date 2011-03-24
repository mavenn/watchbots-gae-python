#!/usr/bin/env python

"""PubSubHubBub Subscriber implementation

Inital implementation based on Nick Johnson's post:
http://blog.notdot.net/2010/02/Consuming-RSS-feeds-with-PubSubHubbub

with additional parts derived from:
djpubsubhubbub - https://bitbucket.org/petersanchez/djpubsubhubbub
PubSubHubBub reference implementation - http://code.google.com/p/pubsubhubbub/
"""

import base64
import hashlib
import logging
import random
import urllib
import urlparse
import wsgiref.handlers
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from django.utils import simplejson

from lib import feedparser

from lib.watchbot import BaseHandler
from models import FeedStream, FeedItem
from config import *


class SubscriberHandler(webapp.RequestHandler):
  """Handler to process new feed subscriptions from our callers"""
  def post(self):
    stream = FeedStream.get(db.Key(self.request.POST.get("key")))
    if stream is None:
      logging.warn("feedstream not found for subscription request")
      self.response.out.write("feedstream not found for subscription request")
      self.error(404)
      return

    feed = feedparser.parse(stream.url)
    if hasattr(feed, 'feed') and hasattr(feed.feed, 'links'):
      hub_url = find_feed_url('hub', feed.feed.links)
      if hub_url is None:
        logging.info("no hub found for: %s" % stream.url)
        self.response.out.write('no hub found')
        return
      else:
        logging.info("sending pshb subscription request for: %s" % stream.url)
        stream.pshb_hub_url = hub_url
        stream.put()
        self.subscribe_to_topic(stream, hub_url)
        self.response.out.write('sent subscription request')
        return

    logging.warn('could not parse feed unable to initiate subscription')
    self.response.out.write('could not parse feed unable to initiate subscription')
    self.error(400)

  def subscribe_to_topic(self, stream, hub_url):
    """Execute subscription request to the hub"""
    callback_url = urlparse.urljoin(self.request.url, "/subscriber/callback/%s" % stream.stream_id)
    logging.info(callback_url)
    subscribe_args = {
        'hub.callback': callback_url,
        'hub.mode': 'subscribe',
        'hub.topic': stream.url,
        'hub.verify': 'async',
        'hub.verify_token': stream.pshb_verify_token,
    }
    response = urlfetch.fetch(hub_url, payload=urllib.urlencode(subscribe_args),
                              method=urlfetch.POST, headers={})
    logging.debug(response.status_code)
    logging.debug(response.headers)
    logging.debug(response.content)
    return response
 

class CallbackHandler(webapp.RequestHandler):
  """Handler for subscription and update callbacks"""
  def get(self, stream_id):
    mode = self.request.GET['hub.mode']
    topic = self.request.GET['hub.topic']
    challenge = self.request.GET['hub.challenge']
    verify_token = self.request.GET['hub.verify_token']
    
    feedstream = FeedStream.get_by_key_name("z%s" % stream_id)
    if feedstream is None:
      logging.warn("feedstream not found in pshb subscription callback: %s" % topic)
      self.error(404)
      return
    if mode == 'unsubscribe':
      logging.info("pshb unsubscribe callback for %s" % topic)
      feedstream.pshb_is_subscribed = False
      feedstream.put()
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write(challenge)
      return
    if mode != 'subscribe':
      logging.warn("pshb mode unknown %s" % mode)
      self.error(400)
      return
    if feedstream.pshb_verify_token != verify_token:
      logging.warn("verify token's don't match. topic: %s verify_token: %s" % (topic, verify_token))
      self.error(400)
      return
    logging.info("pshb topic subscription callback for %s" % topic)
    feedstream.pshb_is_subscribed = True
    feedstream.put()
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(challenge)

  def post(self, stream_id):
    """Handles Content Distribution notifications."""
    logging.debug(self.request.headers)

    feed = feedparser.parse(self.request.body)
    if feed.bozo:
      logging.error('Bozo feed data. %s: %r',
                     feed.bozo_exception.__class__.__name__,
                     feed.bozo_exception)
      if (hasattr(feed.bozo_exception, 'getLineNumber') and
          hasattr(feed.bozo_exception, 'getMessage')):
        line = feed.bozo_exception.getLineNumber()
        logging.error('Line %d: %s', line, feed.bozo_exception.getMessage())
        segment = self.request.body.split('\n')[line-1]
        logging.info('Body segment with error: %r', segment.decode('utf-8'))
      return self.response.set_status(500)

    feedstream = FeedStream.get_by_key_name("z%s" % stream_id)
    if feedstream is None:
      logging.warn("Discarding update from unknown feed '%s'", stream_id)
      self.error(404)
      return

    logging.info("Processing update for feed '%s'", feedstream.url)
    logging.info('Found %d entries', len(feed.entries))

    to_put = []  # batch datastore updates
    for entry in feed.entries:
      item = FeedItem.process_entry(entry, feedstream)
      if item is not None:
        to_put.append(item)
    if len(to_put) > 0:
      db.put(to_put)
      self.update_mavenn_activity(feedstream.stream_id, to_put)

    # Response headers (body can be empty) 
    # X-Hub-On-Behalf-Of
    self.response.set_status(200)
    self.response.out.write("ok");

  def update_mavenn_activity(self, stream_id, items):
    mavenn_activity_update = {"status": "active", "stream_id": stream_id}
    activities = []
    for item in items:
      activities.append(item.to_activity())
    mavenn_activity_update["activity"] = activities
    activity = simplejson.dumps(mavenn_activity_update)
    
    logging.debug("notifying mavenn")
    url = MAVENN_API_URL % stream_id
    pair = "%s:%s" % (FEEDBOT_MAVENN_API_KEY, FEEDBOT_MAVENN_AUTH_TOKEN)
    token = base64.b64encode(pair)
    headers = {"Content-Type": "application/json", "Authorization": "Basic %s" % token}
    #logging.debug(headers)
    #logging.debug(activity)
    result = urlfetch.fetch(url, payload=activity, method=urlfetch.POST,headers=headers)
    logging.debug(result.status_code)
    logging.debug(result.headers)
    logging.debug(result.content)


def find_feed_url(linkrel, links):
  for link in links:
    if link.rel == linkrel:
      return link.href
  return None


def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([
          (r'/subscriber/subscribe', SubscriberHandler),
          (r'/subscriber/callback/(.*)', CallbackHandler),
          ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
