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
  # eachDefaultSystem is effectively a copy and paste of the same config multiple times,
  # with the main difference being the system, which for our purposes includes x86 and arm64 linux.
  # should allow for users of nix on macos to build there, but I'm not testing it.
    utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      poetry2nix = inputs.poetry2nix.lib.mkPoetry2Nix {inherit pkgs;};
      machine_shop = self.packages.${system}.machine_shop;
      sync_cmd = "${machine_shop}/bin/sync";
      overrides = poetry2nix.overrides.withDefaults (final: prev: {
        # prefer binary wheels instead of source distributions for rust based dependencies
        # avoids needing to build them from source. technically a security risk
        polars = prev.polars.override {
          preferWheel = true;
        };
        ruff = prev.ruff.override {
          preferWheel = true;
        };
        # override to make sure setuptools is present for the canvasapi package
        canvasapi = prev.canvasapi.overridePythonAttrs (old: {
          buildInputs = (old.buildInputs or []) ++ [prev.setuptools];
        });
        # override to make sure the flit build system is present for itsdangerous
        itsdangerous = prev.itsdangerous.overridePythonAttrs (old: {
          buildInputs = (old.buildInputs or []) ++ [prev.flit];
        });
      });
      # if you don't want the default that nixpkgs is supplying to you (as of april 2022, 3.11.8),
      # you must manually specify it. the desired version will not be sourced from poetry.lock
      python_version = pkgs.python312;
    in {
      packages = {
        # defines how to build the docker image. by referencing sync_cmd, which references
        # machine_shop (a package defined below), we guarantee that everthing needed is included
        # in the docker image without needing to specify it.
        dockerImage = pkgs.dockerTools.buildImage {
          name = "sync";
          tag = "latest";
          config = {
            Cmd = [sync_cmd];
          };
        };

        # defines the poetry application that we want to build
        # reads in pyproject.toml and poetry.lock to do this
        machine_shop = poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          overrides = overrides;
          python = python_version;
        };

        # a nix idiom where default has a special meaning, so if you run
        # nix build . then this is what will get built
        default = machine_shop;
      };

      # defines the default development environment we want nix to make us
      # it's essentially identical to the machine_shop package, except we specify
      # the three modules we want to be editable in the development environment.
      # if this was not done, you'd need to rebuild the shell every time you make a
      # change and want to see it reflected, and debugging would be horrific (believe me I tried it)
      # the editable packages correspond to what's in pyproject.toml
      devShells.default = let
        env = poetry2nix.mkPoetryEnv {
          projectDir = ./.;
          overrides = overrides;
          python = python_version;
          editablePackageSources = {
            sync = ./sync;
            forward = ./forward;
            export = ./export;
            jsonl_formatter = ./jsonl_formatter;
          };
        };
      in
        env.env.overrideAttrs (old: {
          nativeBuildInputs =
            (old.nativeBuildInputs or [])
            ++ [
              # add extra packages you want available in the dev env
              pkgs.poetry
              pkgs.just
              pkgs.dive
              pkgs.nodePackages.prettier
            ];
        });

      # defines applications that could be ran with nix run
      # currently goes unused, but is in interesting exercise in how you'd do it
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
        forward = {
          type = "app";
          program = "${machine_shop}/bin/forward";
        };
        sync = sync;
        default = sync;
      };
    });
}
