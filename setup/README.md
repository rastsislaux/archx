# archx setup (new)

This directory contains a small, declarative setup runner for Arch Linux.

- Config files live in `setup/config/` and are loaded **recursively**.
- Each `*.json` file contains a list of command objects (or `{ "version": 1, "commands": [...] }`).
- The runner is **idempotent**: it checks current state before changing anything.

## Quick start

Run everything:

```bash
./setup/run.sh
```

Dry-run (log what would happen):

```bash
./setup/run.sh --dry-run
```

Non-interactive (never prompt; default is to **skip** symlink conflicts):

```bash
./setup/run.sh --non-interactive
```

## Command kinds

### package

Ensures a pacman package is installed.

Example:

```json
{ "kind": "package", "name": "greetd" }
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

## Backends

Backends are pluggable per command:

- `package`: `pacman`
- `service`: `systemctl`
- `symlink`: `ln`

You can override via `backend` in a command object, e.g.:

```json
{ "kind": "package", "name": "git", "backend": "pacman" }
```


