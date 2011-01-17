#!/usr/bin/env python


"""PubSubHubBub Subscriber implementation

Inital implementation based on Nick Johnson's post:
http://blog.notdot.net/2010/02/Consuming-RSS-feeds-with-PubSubHubbub
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

import models
from lib import feedparser


class SubscriberHandler(webapp.RequestHandler):
  """Handler to process new feed subscriptions"""
  def post(self):
    feed = models.FeedStream.get(db.Key(self.request.POST.get("key")))
    hub_url = self.get_hub_url(feed)
    if hub_url is None:
      logging.info("no hub found for: %s" % feed.url)
      self.response.out.write('no hub found')
    else:
      logging.info("sending pshb subscription request for: %s" % feed.url)
      self.subscribe_to_topic(feed, hub_url)
      self.response.out.write('sent subscription request')

  def get_hub_url(self, feed):
    # try to extract it too
    return 'http://pubsubhubbub.appspot.com/subscribe'

  def subscribe_to_topic(self, feed, hub_url):
    callback_url = urlparse.urljoin(self.request.url, '/subscriber/callback')
    logging.info(callback_url)
    subscribe_args = {
        'hub.callback': callback_url,
        'hub.mode': 'subscribe',
        'hub.topic': feed.url,
        'hub.verify': 'async',
        'hub.verify_token': feed.verify_token,
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
    if self.request.GET['hub.mode'] == 'unsubscribe':
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write(self.request.GET['hub.challenge'])
      return
      
    if self.request.GET['hub.mode'] != 'subscribe':
      self.error(400)
      return
 
    topic = self.request.GET['hub.topic']
    logging.info("pshb topic subscription callback for %s" % topic)
    
    feed = models.FeedStream.all().filter('url = ', topic).get()
    if not feed or feed.verify_token != self.request.GET['hub.verify_token']:
      logging.warn("no feed found for pshb topic subscription callback with url: %s" % topic)
      self.error(400)
      return
 
    # update the feed
    feed.pshb_is_subscribed = True
    feed.put()

    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(self.request.GET['hub.challenge'])

  def post(self):
    """Handles new content notifications."""
    logging.debug(self.request.headers)
    logging.debug(self.request.body)
    #feed = feedparser.parse(self.request.body)
    #url = find_self_url(feed.feed.links)
    #feed = models.FeedStream.all().filter('url = ', url).get()
    #if not feed:
    #  logging.warn("Discarding update from unknown feed '%s'", url)
    #  return
    #for entry in feed.entries:
    #  message = "%s (%s)" % (entry.title, entry.link)
    self.response.out.write("ok")


def find_self_url(links):
  for link in links:
    if link.rel == 'self':
      return link.href
  return None    
    

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([
          (r'/subscriber/subscribe', SubscriberHandler),
          (r'/subscriber/callback', CallbackHandler)
          ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
