#!/bin/sh

BASEDIR=$(dirname "$0")
cd $BASEDIR/..
echo Current Directory:
pwd

ollama pull qwen2.5:72b

./scripts/eval-model.sh qwen2.5:72b

ollama pull qwen2.5:7b

./scripts/eval-model.sh qwen2.5:7b

ollama create functionary-small -f ./modelfiles/functionary-small.txt

./scripts/eval-model.sh functionary-small

ollama create functionary-medium -f ./modelfiles/functionary-medium.txt

./scripts/eval-model.sh functionary-medium
