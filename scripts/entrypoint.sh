#!/bin/sh
set -e

if [ -f /usr/local/bin/tailwindcss ]; then
    /usr/local/bin/tailwindcss \
        -i /app/app/blueprints/core/static/css/src/tailwind-input.css \
        -o /app/app/blueprints/core/static/css/tailwind.css \
        -c /app/tailwind.config.js \
        --minify 2>&1
fi

exec "$@"
