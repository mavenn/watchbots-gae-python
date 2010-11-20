This is an H1
=============

This is a working implementation of a Mavenn stream bot framework for Google App Engine.  You can use it to begin building your own bots.

A sample bot, feebot, is included to show a fully functioning bot.  This is the bot currently powering the Feed Streams on Mavenn.


Download and install the App Engine SDK

http://code.google.com/appengine/downloads.html


Create a new App Engine application

http://appengine.google.com


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

