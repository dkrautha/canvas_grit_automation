_default:
    just --list

build_nix:
    nix build .

run_sync_nix:
    nix run .#sync

run_export_nix:
    nix run .#export

run_filebrowser_nix:
    nix run .#filebrowser -- --address=0.0.0.0 -r $HOME

build_docker:
    nix build .#dockerImage
    docker load < result

run_docker_sync: build_docker
    bash docker_wrapper.sh