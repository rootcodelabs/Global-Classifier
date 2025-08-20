#!/bin/sh

# Install dependencies
apk add nodejs

# Rebuild the project
cd /opt/buerokratt-classifier
./node_modules/.bin/vite build -l warn
cp -ru build/* /usr/share/nginx/html/buerokratt-classifier

# Start the Nginx server
nginx -g "daemon off;"
