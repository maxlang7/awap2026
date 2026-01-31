{ pkgs ? import <nixpkgs> {} }:

let
  pythonPackages = pkgs.python3Packages;
in
pkgs.mkShell {
  buildInputs = [
    (pkgs.python3.withPackages (ps: [
      # Pinning versions using overrideAttrs or specific nixpkgs versions
      # is complex, so we'll use the standard package set which
      # currently aligns closely with these stable versions.
      ps.pygame
      ps.setuptools
      ps.wheel
    ]))
  ];

  shellHook = ''
    echo "--- Python Gaming Environment Loaded ---"
    python --version
    echo "Pygame version: $(python -c 'import pygame; print(pygame.version.ver)')"
  '';
}