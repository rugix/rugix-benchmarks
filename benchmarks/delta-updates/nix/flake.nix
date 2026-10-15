{
  description = "Reproduce the Debian delta-update byte simulations";

  inputs = {
    nixpkgs.url = "https://releases.nixos.org/nixpkgs/nixpkgs-26.11pre1088030.8edc0c72e3a3/nixexprs.tar.zst";
    rugix = {
      url = "github:rugix/rugix/b82749ff34ee8668fb3e53322af039a083e8bf69";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, rugix }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      bundler = pkgs.rustPlatform.buildRustPackage {
        pname = "rugix-benchmark-tools";
        version = "b82749f";
        src = rugix;
        cargoBuildFlags = [ "--bin" "rugix-ctrl" "--bin" "rugix-bundler" ];
        cargoLock = {
          lockFile = rugix + "/Cargo.lock";
          allowBuiltinFetchGit = true;
        };
        nativeBuildInputs = [ pkgs.pkg-config ];
        buildInputs = [ pkgs.xz ];
        env.RUGIX_GIT_VERSION = "b82749f";
        doCheck = false;
      };
    in {
      packages.${system}.default = bundler;
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          bundler pkgs.xz pkgs.xdelta
          (pkgs.python313.withPackages (ps: [ ps.click ps.matplotlib ]))
        ];
      };
    };
}
