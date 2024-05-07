_default:
    just --list

nix_build:
    nix build .

nix_run_sync:
    nix run .#sync

docker_build:
    nix build .#dockerImage
    docker load < result

docker_run: docker_build
    bash docker_wrapper.sh