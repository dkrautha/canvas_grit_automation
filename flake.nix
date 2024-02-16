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
    in {
      packages = {
        canvas = mkPoetryApplication {
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

        default = self.packages.${system}.canvas;
      };

      devShells.default = pkgs.mkShell {
        inputsFrom = [self.packages.${system}.canvas];
        packages = [pkgs.poetry];
      };

      apps = {
        filebrowser = {
          type = "app";
          program = "${pkgs.filebrowser}/bin/filebrowser";
        };
        default = {
          type = "app";
          program = "${self.packages.${system}.canvas}/bin/canvas";
        };
      };
    });
}
