_default:
    just --list

build_nix:
    nix build .

run_sync:
    nix run .#sync

run_export:
    nix run .#export

run_filebrowser:
    nix run .#filebrowser -- --address=0.0.0.0 -r $HOME

build_docker:
    nix build .#dockerImage
    docker load < result

run_docker: build_docker
    docker run --rm --env-file ./.env \
        -v ./logs:/logs \
        -v ./backup:/backup \
        --user $(id -u):$(id -g) \
        canvas:latest
