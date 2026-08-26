{
  description = "Reverse-engineering environment for the Philips VP415 / VP410 ROM images";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (pkgs:
        let
          # Python for the data-extraction side: Pillow renders candidate
          # character sets, numpy/matplotlib for entropy and structure plots.
          pythonEnv = pkgs.python3.withPackages (ps: with ps; [
            pillow
            numpy
            matplotlib
          ]);

          # A shell helper from tools/, with its dependencies on PATH.
          shellTool = name: runtimeInputs:
            pkgs.writeShellApplication {
              inherit name runtimeInputs;
              text = builtins.readFile (./tools + "/${name}");
            };

          vp-arch = shellTool "vp-arch" [ ];

          vp-sum16 = shellTool "vp-sum16" [ pkgs.python3 pkgs.coreutils pkgs.gnugrep ];

          vp-dis = shellTool "vp-dis" [ pkgs.mame-tools vp-arch pkgs.coreutils ];

          vp-ghidra = shellTool "vp-ghidra" [ pkgs.ghidra vp-arch pkgs.coreutils ];

          vp-fontdump = pkgs.runCommand "vp-fontdump" { } ''
            mkdir -p $out/bin
            substitute ${./tools/vp-fontdump.py} $out/bin/vp-fontdump \
              --replace-fail '#!/usr/bin/env python3' '#!${pythonEnv}/bin/python3'
            chmod +x $out/bin/vp-fontdump
          '';

          vp-lvdos = pkgs.runCommand "vp-lvdos" { } ''
            mkdir -p $out/bin
            substitute ${./tools/vp-lvdos.py} $out/bin/vp-lvdos \
              --replace-fail '#!/usr/bin/env python3' '#!${pythonEnv}/bin/python3'
            chmod +x $out/bin/vp-lvdos
          '';

          vp-mcs51 = pkgs.runCommand "vp-mcs51" { } ''
            mkdir -p $out/bin
            substitute ${./tools/vp-mcs51.py} $out/bin/vp-mcs51 \
              --replace-fail '#!/usr/bin/env python3' '#!${pythonEnv}/bin/python3'
            chmod +x $out/bin/vp-mcs51
          '';
        in
        {
          inherit vp-arch vp-sum16 vp-dis vp-ghidra vp-fontdump vp-lvdos vp-mcs51 pythonEnv;

          # Every helper in one derivation, for `nix profile install`.
          vp-tools = pkgs.symlinkJoin {
            name = "vp-tools";
            paths = [ vp-arch vp-sum16 vp-dis vp-ghidra vp-fontdump vp-lvdos vp-mcs51 ];
          };

          default = self.packages.${pkgs.stdenv.hostPlatform.system}.vp-tools;
        });

      devShells = forAllSystems (pkgs:
        let
          inherit (self.packages.${pkgs.stdenv.hostPlatform.system})
            vp-arch vp-sum16 vp-dis vp-ghidra vp-fontdump vp-lvdos vp-mcs51 pythonEnv;

          helpers = [ vp-arch vp-sum16 vp-dis vp-ghidra vp-fontdump vp-lvdos vp-mcs51 ];

          # Disassembly and static analysis.
          #
          #   mame-tools  unidasm covers all three CPUs in this player (upi41,
          #               i8051, z80) from one binary, and brings ldverify /
          #               ldresample / romcmp / chdman along with it.
          #   rizin       scriptable CLI analysis; 8051 with ESIL emulation,
          #               Z80 disassembly. Good for batch questions and diffing.
          disassembly = [
            pkgs.mame-tools
            pkgs.rizin
          ];

          # Assembly, for proving a disassembly is right by rebuilding it.
          #
          #   asl         Alfred Arnold's macro assembler: MCS-48, MCS-51 and
          #               Z80 all from one tool, with p2bin/p2hex to get a flat
          #               image back out to compare byte-for-byte.
          assembly = [
            pkgs.asl
          ];

          # Image handling and formats.
          #
          #   srecord     Intel HEX <-> binary, splitting, filling, checksums.
          #               The two 8041 dumps only exist as .hex upstream.
          formats = [
            pkgs.srecord
          ];

          # Looking at bytes and comparing revisions. Four of the eleven images
          # are earlier/later revisions of another, so diffing earns its place.
          inspection = [
            pkgs.hexyl
            pkgs.vbindiff
            pkgs.ripgrep
            pkgs.imagemagick
          ];

          # Writing it all up.
          documentation = [
            pkgs.graphviz
          ];

          cli = disassembly ++ assembly ++ formats ++ inspection ++ documentation
            ++ [ pythonEnv ] ++ helpers;

          banner = tools: ''
            echo ""
            echo "  VP415 / VP410 ROM reverse-engineering shell"
            echo ""
            echo "  helpers   vp-arch     what CPU, what load address, what to watch out for"
            echo "            vp-sum16    verify an image against Philips' sum16"
            echo "            vp-dis      linear disassembly with the right arch preselected"
            echo "            vp-fontdump render ROM regions as bitmaps (find the OSD font)"
            echo "            vp-lvdos    decode module W's LV-DOS byte code"
            echo "            vp-mcs51    disassemble the 8051 ROMs, tables resolved"
            ${tools}
            echo ""
            echo "  start     vp-sum16 original-images/*.bin"
            echo "            vp-arch original-images/*.bin"
            echo ""
          '';
        in
        {
          default = pkgs.mkShell {
            name = "vp415-re";
            packages = cli ++ [ pkgs.ghidra ];
            shellHook = banner ''
              echo "            vp-ghidra   import into Ghidra with language and base set"
              echo ""
              echo "  also      unidasm rizin asl p2bin srec_cat hexyl vbindiff ghidra"
            '';
          };

          # Same thing without Ghidra's ~700 MB download, for quick CLI work.
          lite = pkgs.mkShell {
            name = "vp415-re-lite";
            packages = cli;
            shellHook = banner ''
              echo ""
              echo "  also      unidasm rizin asl p2bin srec_cat hexyl vbindiff"
              echo "            (no Ghidra in this shell -- use 'nix develop' for that)"
            '';
          };
        });

      formatter = forAllSystems (pkgs: pkgs.nixpkgs-fmt);
    };
}
