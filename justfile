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

copy_services:
    cp services/* ~/.config/systemd/user/
    systemctl --user daemon-reload

enable_filebrowser_service:
    systemctl --user enable --now filebrowser.service

enable_sync_timer:
    systemctl --user enable --now canvas_grit_sync.timer

build_docker:
    nix build .#dockerImage
    docker load < result

run_docker_sync: build_docker
    docker run --rm --env-file ./.env \
        -v ./logs:/logs \
        -v ./backup:/backup \
        --user $(id -u):$(id -g) \
        sync:latest