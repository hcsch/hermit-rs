{
  inputs = {
    nixpkgs.url = "nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      rust-overlay,
    }:

    let
      # Use same nightly compiler as for hermit
      toolchain =
        pkgs:
        pkgs.rust-bin.nightly."2025-05-16".default.override {
          extensions = [ "rust-src" ];
        };
      rustPlatform =
        pkgs:
        pkgs.makeRustPlatform {
          rustc = toolchain pkgs;
          cargo = toolchain pkgs;
        };
    in
    {
      nixosConfigurations.dyn-mem = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [
          {
            nixpkgs.overlays = [ rust-overlay.overlays.default ];
          }
          (
            {
              config,
              lib,
              pkgs,
              modulesPath,
              ...
            }:

            let
              dyn-mem = (rustPlatform pkgs).callPackage ./dyn-mem.nix { };
            in
            {
              system.configurationRevision = self.rev or "dirty";
              system.stateVersion = "25.05";

              users.users.root.password = "root";

              environment.systemPackages = [ dyn-mem ];

              boot.initrd.availableKernelModules = [
                "virtio_pci"
              ];
              boot.initrd.kernelModules = [
                "virtio_balloon"
                "virtio_console"
                "virtio_rng"
              ];

              boot.kernelParams = [ "console=ttyS1" ];
              boot.loader.grub = {
                device = "/dev/vda";
                timeoutStyle = "hidden";
              };
              boot.loader.timeout = 0;

              fileSystems."/" = {
                device = "/dev/disk/by-label/nixos";
                autoResize = true;
                fsType = "ext4";
              };

              system.build.qcow2 = import "${modulesPath}/../lib/make-disk-image.nix" {
                inherit lib config pkgs;
                diskSize = 4096;
                format = "qcow2";
                partitionTableType = "hybrid";
              };

              systemd.services.dyn-mem = {
                wantedBy = [ "multi-user.target" ];
                serviceConfig = {
                  Type = "exec";
                  ExecStart = "${lib.getBin dyn-mem}/bin/dyn_mem";
                  ExecStopPost = "systemctl poweroff";
                  StandardOutput = "tty";
                  StandardError = "inherit";
                  TTYPath = "/dev/ttyS0";
                };
              };
            }
          )
        ];
      };

      packages.x86_64-linux = rec {
        default = dyn-mem;
        dyn-mem =
          (rustPlatform (
            import nixpkgs {
              system = "x86_64-linux";
              overlays = [ rust-overlay.overlays.default ];
            }
          )).callPackage
            ./dyn-mem.nix
            { };
      };
    };
}
