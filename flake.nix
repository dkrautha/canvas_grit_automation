{
  description = "A Nix-flake-based Python development environment";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.flake-utils.follows = "flake-utils";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    poetry2nix,
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      inherit (poetry2nix.lib.mkPoetry2Nix {inherit pkgs;}) mkPoetryApplication overrides;
      machine_shop = self.packages.${system}.machine_shop;
      sync_cmd = "${machine_shop}/bin/sync";
    in {
      packages = {
        dockerImage = pkgs.dockerTools.buildImage {
          name = "sync";
          tag = "latest";
          config = {
            Cmd = [sync_cmd];
          };
        };

        machine_shop = mkPoetryApplication {
          projectDir = self;
          overrides = overrides.withDefaults (final: prev: {
            polars = prev.polars.override {
              preferWheel = true;
            };
            canvasapi = prev.canvasapi.overridePythonAttrs (old: {
              buildInputs = (old.buildInputs or []) ++ [prev.setuptools];
            });
          });
        };

        default = machine_shop;
      };

      devShells.default = pkgs.mkShell {
        inputsFrom = [machine_shop];
        packages = [pkgs.poetry];
      };

      apps = let
        sync = {
          type = "app";
          program = sync_cmd;
        };
      in {
        filebrowser = {
          type = "app";
          program = "${pkgs.filebrowser}/bin/filebrowser";
        };
        export = {
          type = "app";
          program = "${machine_shop}/bin/export";
        };
        sync = sync;
        default = sync;
      };
    });
}
