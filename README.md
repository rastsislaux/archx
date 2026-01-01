# archx

`archx` is my personal set of scripts/configs to set up a fresh Arch Linux system the way I like it.

The setup is driven by **`archx-setup`**, a small declarative runner living in `setup/`.
For details about how the runner works and how to extend it, see `setup/README.md`.

## What is this “for”?

The goal is to be able to rebuild my environment on a fresh Arch install by editing declarative configs (mostly packages/services/symlinks), keeping everything **idempotent**.

Think “a NixOS-like workflow”, but:

- still **Arch-based**
- mostly **binary packages** (pacman / AUR via yay), not rebuilding the whole OS from source
- easy to fork and maintain your own “spin”

## How to run

From the repo root:

```bash
./archx-install
```

Dry-run:

```bash
./archx-install --dry-run
```

## How to customize (recommended workflow)

- Fork this repo.
- Edit config files in `archx/` (`*.toml`, `*.json`, `*.yaml`, `*.yml`):
  - add/remove packages
  - add/remove symlinks into your dotfiles
  - enable services
  - keep changes idempotent (commands should be safe to re-run)
- Keep actual dotfiles/config payloads in `dotfiles/` and reference them via `[[symlink]] source = "dotfiles/..."`.

## What changes does `archx-setup` apply?

Important notes:

- The exact outcome depends on your flags (e.g. `--symlink-conflict`) and any saved decisions in `${XDG_CONFIG_HOME:-~/.config}/archx-setup/decisions.json`.
- Some steps are implemented as `[[shell]]` scripts (see below).

### Components (what you get)

| Category | Choice / Component |
|---|---|
| Compositor | `hyprland` |
| Hyprland plugins | `hyprpm` + `hyprexpo` |
| Panel | `waybar` |
| Notifications | `swaync` |
| Browser | `chromium` |
| Terminal | `kitty` |
| Editor | `lite-xl` |
| File manager | `yazi` |
| Image viewer | `swayimg` |
| Display manager | `greetd` + `greetd-tuigreet` |
| Screenshots | `grimblast-git` (AUR via `yay`) |
| AUR helper | `yay` |
| App launcher | `vicinae-bin` (AUR via `yay`) |
| Vicinae plugins/extensions | pulseaudio, wifi-commander, bluetooth |

### Build/tooling groups installed

| Group | Packages |
|---|---|
| Build essentials / AUR builds | `base-devel`, `gcc`, `cmake`, `meson`, `cpio`, `git` |
| JS toolchain (used by extension builds) | `npm` |
| Desktop utilities | `brightnessctl`, `jq`, `libnotify` |
| Fonts | `noto-fonts`, `otf-font-awesome` |

### Packages installed (complete list)

The following packages are ensured to be installed by the configs under `archx/`:

- **pacman**:
  - `base-devel`
  - `brightnessctl`
  - `chromium`
  - `cmake`
  - `cpio`
  - `gcc`
  - `git`
  - `greetd`
  - `greetd-tuigreet`
  - `hypridle`
  - `hyprland`
  - `hyprlock`
  - `hyprpaper`
  - `jq`
  - `kitty`
  - `libnotify`
  - `lite-xl`
  - `meson`
  - `nano`
  - `networkmanager`
  - `noto-fonts`
  - `noto-fonts-emoji`
  - `npm`
  - `otf-font-awesome`
  - `plymouth`
  - `swayimg`
  - `swaync`
  - `waybar`
  - `yazi`
- **yay** (AUR):
  - `grimblast-git`
  - `vicinae-bin`

### Services enabled

- `NetworkManager.service`
- `greetd.service`

### Symlinks created (repo -> system)

These are ensured as symlinks (if the target path is free or you choose to replace it):

- `~/.config/archx` -> `dotfiles/archx`
- `~/.config/hypr` -> `dotfiles/hypr`
- `~/.config/swaync` -> `dotfiles/swaync`
- `~/.config/vicinae` -> `dotfiles/vicinae`
- `~/.config/waybar` -> `dotfiles/waybar`
- `~/.config/yazi` -> `dotfiles/yazi`
- `/etc/greetd` -> `dotfiles/greetd`
- `/etc/mkinitcpio.conf.d/000_plymouth.conf` -> `dotfiles/mkinitcpio/000_plymouth.conf`

 
