#!/bin/sh

BASEDIR=$(dirname "$0")
cd $BASEDIR/..
echo Current Directory:
pwd

export MODEL=$1
echo Evaluating $MODEL

export PYTHONPATH="."

export BASE_URL=""
export FINANCE_CLERK_MODEL=$MODEL
export SUPERVISOR_MODEL=$MODEL
export SQL_MODEL=$MODEL

export VISION_BASE_URL=""
export VISION_MODEL=$MODEL

python app.py
