_default:
    just --list

setup:
    mkdir -p .venv/ && pdm install

activate: setup
    eval $(pdm venv activate)

build: setup
    pdm build 

run: setup activate
    machine_shop