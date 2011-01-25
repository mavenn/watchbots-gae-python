#!/usr/bin/env python

"""PubSubHubBub Subscriber implementation

Inital implementation based on Nick Johnson's post:
http://blog.notdot.net/2010/02/Consuming-RSS-feeds-with-PubSubHubbub

with additional parts derived from djpubsubhubbub:
https://bitbucket.org/petersanchez/djpubsubhubbub
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
  """Handler to process new feed subscriptions"""
  def post(self):
    feed = FeedStream.get(db.Key(self.request.POST.get("key")))
    hub_url = self.get_hub_url(feed)
    if hub_url is None:
      logging.info("no hub found for: %s" % feed.url)
      self.response.out.write('no hub found')
    else:
      logging.info("sending pshb subscription request for: %s" % feed.url)
      feed.pshb_hub_url = hub_url
      feed.put()
      self.subscribe_to_topic(feed, hub_url)
      self.response.out.write('sent subscription request')

  def get_hub_url(self, feed):
    """Extract hub url from feed"""
    feed = feedparser.parse(feed.url)
    if "links" in feed.feed:
      for link in feed.feed.links:
        if "rel" in link and link.rel == "hub":
          return link.href
    return None

  def subscribe_to_topic(self, feed, hub_url):
    callback_url = urlparse.urljoin(self.request.url, '/subscriber/callback')
    logging.info(callback_url)
    subscribe_args = {
        'hub.callback': callback_url,
        'hub.mode': 'subscribe',
        'hub.topic': feed.url,
        'hub.verify': 'async',
        'hub.verify_token': feed.pshb_verify_token,
    }
    headers = {}
    response = urlfetch.fetch(hub_url, payload=urllib.urlencode(subscribe_args),
                              method=urlfetch.POST, headers=headers)
    logging.debug(response.status_code)
    logging.debug(response.headers)
    logging.debug(response.content)
    return response
 

class CallbackHandler(webapp.RequestHandler):
  """Handler for subscription and update callbacks"""
  def get(self):
    mode = self.request.GET['hub.mode']
    topic = self.request.GET['hub.topic']
    challenge = self.request.GET['hub.challenge']
    verify_token = self.request.GET['hub.verify_token']
    
    feedstream = FeedStream.get_by_url(topic)

    if mode == 'unsubscribe':
      logging.info("pshb unsubscribe callback for %s" % topic)
      if feedstream is not None:
        feed.pshb_is_subscribed = False
        feed.put()
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write(challenge)
      return
      
    if mode != 'subscribe':
      self.error(400)
      return
 
    logging.info("pshb topic subscription callback for %s" % topic)
    
    if not feed or feed.pshb_verify_token != verify_token:
      logging.warn("no feed found for pshb topic subscription callback with url: %s" % topic)
      self.error(400)
      return
 
    feed.pshb_is_subscribed = True
    feed.put()
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(challenge)

  def post(self):
    """Handles Content Distribution notifications."""
    logging.debug(self.request.headers)
    logging.debug(self.request.body)
    feed = feedparser.parse(self.request.body)

    if "links" in feed.feed:
      url = find_self_url(feed.feed.links)
      feedstream = FeedStream.get_by_url(url)

      if not feedstream:
        logging.warn("Discarding update from unknown feed '%s'", url)
        return

      #hub_url = feedstream.pshb_hub_url
      #for link in feed.feed.links:
      #  if link['rel'] == 'hub':
      #    hub_url = link['href']

      #needs_update = False
      #if hub_url and feedstream.pshb_hub_url != hub_url:
      #  # hub URL has changed; let's update our subscription
      #  needs_update = True
      # TODO: topic URL has changed
    
      logging.info("Processing update for known feed '%s'", url)
      to_put = []
      for entry in feed.entries:
        item = FeedItem.process_entry(entry, feedstream)
        if item is not None:
          to_put.append(item)
      if len(to_put) > 0:
        db.put(to_put)
        self.update_mavenn_activity(feedstream.stream_id, to_put)
    
      # Response headers (body is empty) 
      # X-Hub-On-Behalf-Of

  def update_mavenn_activity(self, stream_id, items):
    mavenn_activity_update = {"status": "active", "stream_id": stream_id}
    activities = []
    for item in items:
      activities.append(item.to_activity())
    mavenn_activity_update["activity"] = activities
    activity = simplejson.dumps(mavenn_activity_update)
    
    url = MAVENN_API_URL % stream_id
    pair = "%s:%s" % (FEEDBOT_MAVENN_API_KEY, FEEDBOT_MAVENN_AUTH_TOKEN)
    token = base64.b64encode(pair)
    headers = {"Content-Type": "application/json", "Authorization": "Basic %s" % token}
    result = urlfetch.fetch(url, payload=activity, method=urlfetch.POST,headers=headers)
    logging.debug(result.status_code)
    logging.debug(result.headers)
    #logging.debug(result.content)
    return

def find_self_url(links):
  for link in links:
    if link.rel == 'self':
      return link.href
  return None    


class PHSBCallbackTestHandler(BaseHandler):
  """"""
  def get(self):
    self.generate('pshb-tester.html', {})

  def post(self):
    content_type = self.request.POST['content_type']
    contents = self.request.POST['contents']
    
    result = urlfetch.fetch(url, payload=activity, method=urlfetch.POST,headers=headers)
    callback_url = urlparse.urljoin(self.request.url, '/subscriber/callback')
    
    


def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([
          (r'/subscriber/subscribe', SubscriberHandler),
          (r'/subscriber/callback', CallbackHandler),
          (r'/subscriber/tester', PHSBCallbackTestHandler)
          ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
