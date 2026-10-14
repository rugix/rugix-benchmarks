# Delta-Update Byte Simulations

This is the original delta-update benchmark suite, migrated from `rugix/rugix`. It builds ARM64 Debian Bookworm and Bullseye images at monthly snapshots from June 2023 through June 2025, then estimates download sizes for monthly, quarterly, half-yearly, annual, and Bullseye-to-Bookworm updates.

The suite compares complete-image XZ compression, static xdelta3 patches, fixed-size block reuse, Casync content-defined block reuse, and the experimental deltar approach. Block simulations include compressed indices and a configurable per-group overhead allowance. They estimate bytes and do not measure HTTP requests or native installation time. The [native adaptive-update suite](../adaptive-downloads/README.md) validates selected pairs with actual Rugix and RAUC installs.

## Run the Original Suite

From the repository root, enter the pinned toolchain and build Rugix tools:

```sh
nix develop path:./nix
uv sync --locked
uv run --locked rugix-benchmarks tools
export DOCKER=podman
export RUGIX_BAKERY_IMAGE=ghcr.io/rugix/rugix-bakery@sha256:7c8466d3823db8a012e20d03d523228359b1cce360ee03b3c5b9e14fbc9e11d1
cd delta-updates
uv run --project .. --locked python benchmark.py schedules
uv run --project .. --locked python benchmark.py build
uv run --project .. --locked bash compute-all.sh
uv run --project .. --locked python benchmark.py analyze
```

Building the full two-year corpus requires substantially more storage and time than the selected native benchmark plan. Existing per-image and per-comparison outputs are reused. Compute failures propagate instead of being silently ignored. Set `BENCHMARK_JOBS` to limit parallel simulations; the default is four.

Raw images remain in `build/<suite>/<snapshot>`. Results remain in `results`. These directories are ignored by Git. `RUGIX_BUNDLER` can select another bundler executable; otherwise the suite uses the executable on PATH or the repository's prepared `.cache/bin/rugix-bundler`.

## Model Configurations

| Configuration | Reuse Chunking | Compression Group | Per-Group Allowance |
| --- | --- | --- | ---: |
| RAUC Model | Fixed 4 KiB | 32 KiB or 64 KiB | 768 bytes |
| Casync Model | Content-defined 8, 16, or 64 KiB average | One chunk | 768 bytes |

RAUC's modeled grouping approximates SquashFS compression blocks. Actual bundles also include format metadata, integrity data, and native access patterns. Rugix uses Casync chunking, but a Rugix measurement does not establish the network behavior of the separate casync program. Use the native results to distinguish delivered body bytes from complete interface traffic before selecting correction factors.
