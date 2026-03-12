#!/bin/bash
set -e

echo "Compilation du CSS Tailwind..."
npx -y tailwindcss@3 \
    -i ./app/blueprints/core/static/css/src/tailwind-input.css \
    -o ./app/blueprints/core/static/css/tailwind.css \
    --minify
echo "CSS compilé dans app/blueprints/core/static/css/tailwind.css"
