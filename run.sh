#!/bin/bash

if [ -f bin/proximo ]; then
    exec bin/proximo gunicorn app:app --preload
else
    exec gunicorn app:app --preload
fi
