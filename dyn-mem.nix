{
  lib,
  stdenv,
  cacert,
  buildRustPackage,
  cargo,
  clang,
  llvmPackages,
}:

let
  pname = "dyn-mem";
  version = "0.0.1-alpha";

  src = ./.;

  # Manually build vendor directory as fetchCargoVendor is currently broken for
  # git dependencies relying on workspace inheritance of properties
  # (tokio and workspace.lints in hermit's case)
  # See https://github.com/NixOS/nixpkgs/issues/421657
  cargoVendorOutput = stdenv.mkDerivation {
    inherit version src;
    pname = "${pname}-cargo-vendor";

    nativeBuildInputs = [
      cacert
      cargo
    ];

    dontConfigure = true;

    HERMIT_LOG_LEVEL_FILTER = "info";

    buildPhase = ''
      export CARGO_HOME=$(mktemp -d)

      mkdir -p .cargo

      cargo vendor --versioned-dirs --locked >> .cargo/config.toml
    '';

    installPhase = ''
      mkdir -p $out

      cp -r vendor $out/
      cp .cargo/config.toml $out/
    '';

    doCheck = false;
    dontFixup = true;

    # Fixed output derivation so we are allowed internet access
    outputHashAlgo = "sha256";
    outputHashMode = "recursive";
    # Update hash when Cargo.toml/Cargo.lock files change
    outputHash = "sha256-euuvHxel2KXdqP47ZBl/Z8c2fkFjgEKY1z8YYP0FLKc=";
  };
in
buildRustPackage {
  inherit pname version src;

  postPatch = ''
    mkdir -p .cargo
    cat ${cargoVendorOutput}/config.toml > .cargo/config.toml
    cp -r ${cargoVendorOutput}/vendor ./
  '';

  cargoVendorDir = "vendor";

  buildAndTestSubdir = "examples/dyn-mem";

  nativeBuildInputs = [
    clang
    llvmPackages.bintools
  ];

  buildInputs = [ ];
}
