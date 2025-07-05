{
  inputs = {
    nixpkgs.url = "nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    {
      nixosConfigurations.dyn-mem = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [
          (
            {
              config,
              lib,
              pkgs,
              modulesPath,
              ...
            }:

            let
              dyn-mem = pkgs.callPackage ./dyn-mem.nix { };
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

              boot.kernelParams = [ "console=ttyS0" ];
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
                };
              };
            }
          )
        ];
      };

      packages.x86_64-linux = rec {
        default = dyn-mem;
        dyn-mem = nixpkgs.legacyPackages.x86_64-linux.callPackage ./dyn-mem.nix { };
      };
    };
}
