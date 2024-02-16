#!/usr/bin/env bash

docker run --rm --env-file ./.env \
    -v ./logs:/logs \
    -v ./backup:/backup \
    --user "$(id -u)":"$(id -g)" \
    sync:latest
