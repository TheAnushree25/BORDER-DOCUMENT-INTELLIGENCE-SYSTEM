#!/usr/bin/env bash
# Render Build Script for Python Native Environment
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt
