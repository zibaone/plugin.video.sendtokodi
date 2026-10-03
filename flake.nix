{
  description = "Development shell for plugin.video.sendtokodi (dev branch only — not part of the PR)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" ];

      perSystem = { pkgs, ... }:
        let
          # Only the Kodi addons this plugin actually needs. inputstream.adaptive
          # plays the resolved streams, inputstreamhelper and requests are
          # declared in addon.xml.
          kodiWithPkgs = pkgs.kodi.withPackages (p: with p; [
            inputstream-adaptive
            inputstreamhelper
            requests
          ]);

          pythonEnv = pkgs.python3.withPackages (ps: with ps; [
            pytest
            pytest-cov
            pytest-mock
            requests
          ]);

          runKodiBin = pkgs.writeShellScriptBin "run-kodi" ''
            exec "$PWD/scripts/run_local_kodi.sh" "$@"
          '';
        in {
          devShells.default = pkgs.mkShell {
            name = "sendtokodi-dev";
            buildInputs = [
              kodiWithPkgs
              pythonEnv
              pkgs.deno
              pkgs.ffmpeg
              pkgs.git
              pkgs.curl
              pkgs.xorg-server
              pkgs.xvfb-run
              runKodiBin
            ];

            # Consumed by scripts/run_local_kodi.sh to link the addon
            # dependencies into the throwaway profile.
            KODI_ADDONS_SRC = "${kodiWithPkgs}/share/kodi/addons";

            shellHook = ''
              export PS1="\[\033[1;33m\][sendtokodi]\[\033[0m\]$PS1"
              echo "sendtokodi devShell ready"
              echo "  pytest                    -> unit tests (network tests deselected)"
              echo "  pytest -m network         -> live GitHub release endpoints"
              echo "  run-kodi --headless       -> throwaway Kodi profile, JSON-RPC on 18082"
            '';
          };
        };
    };
}
