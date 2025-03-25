#!/bin/sh

BASEDIR=$(dirname $0)
cd $BASEDIR/..
echo Current Directory:
pwd

export MODEL=$1
echo Evaluating $MODEL

ollama run $MODEL 'hi'
ollama ps

export BASE_URL=http://localhost:11434/v1
export FINANCE_CLERK_MODEL=$MODEL
export SUPERVISOR_MODEL=$MODEL
export SQL_MODEL=$MODEL

export VISION_BASE_URL=http://localhost:11434/v1
export VISION_MODEL=llama3.2-vision:11b

python app.py

ollama stop $MODEL
