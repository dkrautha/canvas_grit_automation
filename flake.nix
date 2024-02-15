{
  description = "A Nix-flake-based Python development environment";

  inputs = {
    nixpkgs.url = "https://flakehub.com/f/NixOS/nixpkgs/0.1.*.tar.gz";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    supportedSystems = ["x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin"];
    forEachSupportedSystem = f:
      nixpkgs.lib.genAttrs supportedSystems (system:
        f {
          pkgs = import nixpkgs {inherit system;};
        });
  in {
    devShells = forEachSupportedSystem ({pkgs}: {
      default = pkgs.mkShell {
        packages = with pkgs;
          [python311 virtualenv pdm filebrowser just]
          ++ (with pkgs.python311Packages; [pip]);
        shellHook = ''
          eval $(pdm venv activate)
        '';
      };
    });
    apps = forEachSupportedSystem ({pkgs}: {
      filebrowser = {
        type = "app";
        program = "${pkgs.filebrowser}/bin/filebrowser";
      };
      default = {
        type = "app";
        program = "${pkgs.just}/bin/just";
      };
    });
  };
}
