_default:
    just --list

setup:
    mkdir -p .venv/ 
    pdm install

activate: 
    source ./.env
    eval $(pdm venv activate)

build: setup
    pdm build 

run:
    machine_shop