#!/bin/sh

BASEDIR=$(dirname "$0")
cd $BASEDIR/..
echo Current Directory:
pwd

ollama create bitagent:8b -f ./modelfiles/bitagent-8b.txt

./scripts/eval-model.sh bitagent:8b

ollama pull hengwen/watt-tool-8B

./scripts/eval-model.sh hengwen/watt-tool-8B

ollama pull hengwen/watt-tool-70B

./scripts/eval-model.sh hengwen/watt-tool-70B

ollama pull command-a:111b

./scripts/eval-model.sh command-a:111b

ollama pull qwen2.5:72b

./scripts/eval-model.sh qwen2.5:72b

ollama pull qwen2.5:7b

./scripts/eval-model.sh qwen2.5:7b

ollama create functionary-small -f ./modelfiles/functionary-small.txt

./scripts/eval-model.sh functionary-small

ollama create functionary-medium -f ./modelfiles/functionary-medium.txt

./scripts/eval-model.sh functionary-medium
