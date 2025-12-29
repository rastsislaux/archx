# archx setup (new)

This directory contains a small, declarative setup runner for Arch Linux.

- Config files live in `setup/config/` and are loaded **recursively**.
- Supported formats: `*.json`, `*.toml`, `*.yaml`, `*.yml`.
  - JSON and TOML work out of the box.
  - YAML requires `PyYAML` (install: `python -m pip install pyyaml`).
- Each config file contains a list of command objects (or `{ "version": 1, "commands": [...] }`).
- The runner is **idempotent**: it checks current state before changing anything.

Example configs in other formats live under `setup/config_examples/` (they are **not** executed by default).

## Quick start

Run everything:

```bash
./setup/archx
```

Dry-run (log what would happen):

```bash
./setup/archx --dry-run
```

Non-interactive (never prompt; default is to **skip** symlink conflicts):

```bash
./setup/archx --non-interactive
```

## Command kinds

### package

Ensures a package is installed.

Example:

```json
{ "kind": "package", "name": "greetd" }
```

Backends:

- default: `pacman`
- AUR: `yay`

Example (AUR):

```json
{ "kind": "package", "backend": "yay", "name": "thorium-browser-bin" }
```

### symlink

Ensures a symlink exists (and points to the expected source).

Example:

```json
{ "kind": "symlink", "source": "config/hypr", "target": "~/.config/hypr" }
```

If the target already exists and is not the desired symlink, the runner will ask what to do.
If you choose **ignore always**, the decision is stored in:

- `${XDG_CONFIG_HOME:-~/.config}/archx-setup/decisions.json`

### service

Ensures a systemd unit is enabled.

Example:

```json
{ "kind": "service", "name": "greetd.service" }
```

### shell

Runs a small bash script (single session, so `cd` works across lines).

Example:

```json
{
  "kind": "shell",
  "stdout": true,
  "stderr": true,
  "script": [
    "echo hello",
    "pwd"
  ]
}
```

## Backends / executors

Command execution is implemented by plugins selected by `(kind, backend)`.

Built-in executors:
- `package`:
  - default backend: `pacman`
  - AUR backend: `yay`
- `service`:
  - default backend: `systemctl`
- `symlink`:
  - default backend: `ln`
- `shell`:
  - default backend: `bash`

You can override via `backend` in a command object, e.g.:

```json
{ "kind": "package", "name": "git", "backend": "pacman" }
```

## Command plugins (runtime-loaded)

Command kinds are implemented as **plugins**, loaded at runtime. Built-in plugins provide:
- `package`
- `service`
- `symlink`
- `shell`

You can add new command kinds without changing core code by dropping a `*.py` file into one of:
- `~/.config/archx-setup/plugins/` (auto-discovered if present)
- any directory passed via `--plugins-dir`
- any directory listed in `ARCHX_SETUP_PLUGINS_DIRS` (path-separated)

Each plugin file must define either:
- `PLUGIN = ...` (preferred), or
- `def get_plugin(): ...`

For a stable plugin SDK (types + utilities like `CommandRunner`), use:
- `archx_setup.plugin_api`

See `setup/plugins_example/echo.py` for a minimal example.


