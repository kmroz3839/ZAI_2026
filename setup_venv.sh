#!/usr/bin/env sh
if [ -d .venv ]; then
    . ./.venv/bin/activate;
else
    python3 -m venv .venv
    chmod +x ./.venv/bin/activate
    . ./.venv/bin/activate
    python -m pip install django
fi

