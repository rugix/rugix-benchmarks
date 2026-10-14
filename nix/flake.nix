{
  description = "Reproducible Rugix delta-update and native HTTP benchmarks";

  inputs = {
    nixpkgs.url = "https://releases.nixos.org/nixpkgs/nixpkgs-26.11pre1088030.8edc0c72e3a3/nixexprs.tar.zst";
    rugix-release = {
      url = "github:rugix/rugix/48fc40d3d903730781f3dc4bf671873d2308573a";
      flake = false;
    };
    rugix-pipeline = {
      url = "github:rugix/rugix/b82749ff34ee8668fb3e53322af039a083e8bf69";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, rugix-release, rugix-pipeline }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      buildRugix = version: src: pkgs.rustPlatform.buildRustPackage {
        pname = "rugix-benchmark-tools";
        inherit version src;
        cargoBuildFlags = [ "--bin" "rugix-ctrl" "--bin" "rugix-bundler" ];
        cargoLock = {
          lockFile = src + "/Cargo.lock";
          allowBuiltinFetchGit = true;
        };
        nativeBuildInputs = [ pkgs.pkg-config ];
        buildInputs = [ pkgs.xz ];
        env.RUGIX_GIT_VERSION = version;
        doCheck = false;
      };
      release = buildRugix "v1.3.0" rugix-release;
      pipeline = buildRugix "b82749f" rugix-pipeline;
      makeIndex = pkgs.stdenv.mkDerivation {
        pname = "rauc-source-index";
        version = "1";
        src = ./make-index.c;
        dontUnpack = true;
        buildInputs = [ pkgs.openssl ];
        buildPhase = "cc -O2 $src -lcrypto -o make-index";
        installPhase = "install -D -m 755 make-index $out/bin/make-index";
      };
      tools = with pkgs; [
        qemu openssl util-linux gptfdisk xz xdelta squashfsTools
        rauc nginx iperf3 tcpdump ethtool
      ];
    in {
      packages.${system} = {
        rugix-release = release;
        rugix-pipeline = pipeline;
        make-index = makeIndex;
        runtime = pkgs.symlinkJoin {
          name = "rugix-benchmark-runtime";
          paths = with pkgs; [ rauc nginx iperf3 tcpdump ethtool makeIndex ];
        };
      };
      devShells.${system}.default = pkgs.mkShell {
        packages = tools ++ [ pipeline pkgs.uv pkgs.python313 pkgs.pkg-config pkgs.gcc pkgs.glib ];
      };
    };
}
