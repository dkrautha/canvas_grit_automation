{
  description = "SIT Machine Shop and MakerSpace Automation";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    utils.url = "github:numtide/flake-utils";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs = {
        flake-utils.follows = "utils";
        nixpkgs.follows = "nixpkgs";
      };
    };
  };

  outputs = inputs @ {
    self,
    nixpkgs,
    utils,
    ...
  }:
    utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      poetry2nix = inputs.poetry2nix.lib.mkPoetry2Nix {inherit pkgs;};
      machine_shop = self.packages.${system}.machine_shop;
      sync_cmd = "${machine_shop}/bin/sync";
      overrides = poetry2nix.overrides.withDefaults (final: prev: {
        polars = prev.polars.override {
          preferWheel = true;
        };
        ruff = prev.ruff.override {
          preferWheel = true;
        };
        canvasapi = prev.canvasapi.overridePythonAttrs (old: {
          buildInputs = (old.buildInputs or []) ++ [prev.setuptools];
        });
      });
      python_version = pkgs.python312;
    in {
      packages = {
        dockerImage = pkgs.dockerTools.buildImage {
          name = "sync";
          tag = "latest";
          config = {
            Cmd = [sync_cmd];
          };
        };

        machine_shop = poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          overrides = overrides;
          python = python_version;
        };

        default = machine_shop;
      };

      devShells.default = let
        env = poetry2nix.mkPoetryEnv {
          projectDir = ./.;
          overrides = overrides;
          python = python_version;
          editablePackageSources = {
            sync = ./sync;
            export_server = ./export_server;
            jsonl_formatter = ./jsonl_formatter;
          };
        };
      in
        env.env.overrideAttrs (old: {
          nativeBuildInputs =
            (old.nativeBuildInputs or [])
            ++ [
              # pkgs.poetry
              pkgs.just
              pkgs.dive
            ];
        });

      apps = let
        sync = {
          type = "app";
          program = sync_cmd;
        };
      in {
        export = {
          type = "app";
          program = "${machine_shop}/bin/export";
        };
        sync = sync;
        default = sync;
      };
    });
}
