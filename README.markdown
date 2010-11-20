# This is an H1 #

This is a working implementation of a Mavenn stream bot framework for Google App Engine.  You can use it to begin building your own bots.  This framework is built to support many bots within a singl GAE application, but feel free to create a single GAE app for your bot if it warrants the resources and makes more sense that way.

A sample bot, feebot, is included to show a fully functioning bot.  This is the bot currently powering the Feed Streams on Mavenn.


## Setup Google App Engine ##


Download and install the App Engine SDK: (http://code.google.com/appengine/downloads.html)


Register a new App Engine application: (http://appengine.google.com)


## Prepare GAE Application ##

Clone this repository

Edit the app.yaml with your application name

Rename config.py.sample to config.py

Register the stream type on Mavenn

http://mavenn.com/springs/new


Update the bot endpoints on Mavenn accordingly.  This framework handles routing for these endpoints.

Stream Resource URL: http://yourapp.appspot.com/yourbot

POST: http://yourapp.appspot.com/yourbot

PUT: http://yourapp.appspot.com/yourbot/stream-id

DELETE: http://yourapp.appspot.com/yourbot/stream-id

GET: http://yourapp.appspot.com/yourbot/stream-id.json

Clean the append .json extension

Leave the "Use POST with _method instead of DELETE or PUT" unchecked


Register the parameters your bot will accept


Get your API Key and Auth Token from Mavenn and update your config.py as needed

Publish your GAE app

