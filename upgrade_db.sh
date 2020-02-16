#!/bin/bash

if [ -f bin/proximo ]; then
    exec bin/proximo flask db upgrade
else
    exec flask db upgrade
fi
