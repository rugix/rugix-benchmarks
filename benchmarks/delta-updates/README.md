# Delta-Update Byte Simulations

This benchmark estimates download sizes for different update techniques at monthly, quarterly, half-yearly, and annual update intervals. It compares complete-image compression, binary patches, and block reuse using two years of ARM64 Debian images.

For installation times and measured HTTP traffic, see the [dynamic delta update benchmark](../dynamic-downloads/README.md).

## Update Models

The corpus contains Bookworm and Bullseye filesystem images built from monthly snapshots between June 2023 and June 2025. Within each Debian release, a schedule represents successive updates, and its aggregate size is the total downloaded over that schedule. The `bullseye-bookworm` scenario pairs a Bullseye source with a Bookworm target independently for each date pair; its aggregate size sums separate major-upgrade estimates.

A static delta is a patch computed for a specific source and target image. A dynamic delta is determined during installation by identifying data the device can reuse from its existing image.

A compression group contains blocks compressed together. Retrieving one missing block can therefore require downloading other data from its group. The benchmark compares complete-image compression with static and dynamic delta techniques:

| Technique | JSON Identifier | Model |
| --- | --- | --- |
| Complete-image XZ | `compression` | Compress the entire target filesystem image. |
| Xdelta | `xdelta` | Use xdelta3 to create a binary patch between source and target images. |
| Fixed-size block reuse | `block-based-fixed-4-768-<group>` | Reuse matching 4 KiB blocks, approximating RAUC's block layout. `<group>` is the compression group size in bytes: `32768` or `65536`. |
| Content-defined block reuse | `block-based-casync-<size>-768` | Use Casync chunking to place block boundaries according to file content. `<size>` is the nominal chunk size in KiB: `8`, `16`, or `64`. This also models Rugix Ctrl's chunking. Each chunk is compressed individually. |
| Deltar | `deltar-…` | Simulate reuse of file contents from tar archives, including a reconstruction plan and compressed new data. The configurations are listed below. |

The block reuse models include compressed indices and add an estimated 768 bytes of transfer overhead per downloaded group.

Deltar chunks each file separately; fixed-size configurations split files into chunks of at most 4 MiB. A group closes after its uncompressed chunk data and length fields exceed the configured byte threshold. Groups can therefore exceed that threshold by the final chunk, and a 1-byte threshold puts each unique chunk in its own group.

| JSON Identifier | Chunking | Group Threshold | Overhead per Group |
| --- | --- | --- | ---: |
| `deltar-casync-16-768-32768` | Content-defined, nominal 16 KiB | 32 KiB | 768 bytes |
| `deltar-fixed-4096-0-1` | Fixed 4 MiB | 1 byte | 0 bytes |
| `deltar-fixed-4096-48-16384` | Fixed 4 MiB | 16 KiB | 48 bytes |

Bundle metadata, integrity data, and HTTP access patterns can affect measured transfers beyond these size estimates.

## Results

For updates within a Debian release, selected configurations produced the following estimated download sizes. Each value is a percentage of complete-image XZ download bytes at the same update interval, averaged equally across Bookworm and Bullseye. Lower values use fewer bytes; 100% equals a complete-image download.

| Configuration | Monthly | Quarterly | Half-Yearly | Annual |
| --- | ---: | ---: | ---: | ---: |
| Xdelta | 12.0% | 18.4% | 23.5% | 27.7% |
| Fixed 4 KiB blocks, 64 KiB compression groups | 26.6% | 43.0% | 57.3% | 67.4% |
| Casync, nominal 16 KiB chunks | 22.9% | 39.1% | 53.0% | 64.3% |
| Deltar, nominal 16 KiB chunks, 32 KiB group threshold | 20.3% | 35.0% | 47.1% | 57.1% |

These results include the overhead estimates specified above. Monthly updates reuse more data per update, while annual updates transfer fewer updates over the same period. For the sampled Bullseye-to-Bookworm upgrades, all four configurations in the table required more bytes than complete-image XZ compression.

The [aggregate data](https://github.com/rugix/rugix-docs/blob/af9e47b669fcfabe0df783008adb4ce7a20e542e/src/components/delta-savings-data.ts) contains compression factors and total byte counts for every configuration and scenario. The [published analysis](https://rugix.org/blog/efficient-delta-updates/) includes graphs of relative efficiency and cumulative download sizes.

## Reproduce the Estimates

Use x86-64 Linux with Nix, flakes enabled, and Docker or Podman. The pinned Nix environment provides Python, Rugix Bundler's simulator, XZ, and xdelta3.

Run the following commands from `benchmarks/delta-updates`. They select Podman for image builds; use `DOCKER=docker` to select Docker.

```sh
nix develop path:./nix
export DOCKER=podman
export RUGIX_BAKERY_IMAGE=ghcr.io/rugix/rugix-bakery@sha256:7c8466d3823db8a012e20d03d523228359b1cce360ee03b3c5b9e14fbc9e11d1

python benchmark.py schedules
python benchmark.py build
bash compute-all.sh
python benchmark.py analyze
```

The commands list the update pairs, build the filesystem images, compute estimates for every technique, and print aggregated results. The final command prints two JSON objects, labeled `Compression Factors` and `Total Sizes`:

- **Compression Factors:** summed estimated update bytes divided by summed uncompressed target bytes across the image pairs in each schedule. Smaller ratios mean less data to transfer.
- **Total Sizes:** estimated update bytes summed for each scenario and schedule, in bytes.

Both objects are grouped by Debian release or upgrade scenario, update schedule, and technique. Deltar identifiers ending in `-plan` or `-data` report the reconstruction plan or compressed data separately; identifiers without those suffixes report their sum.

## Files and Options

Image builds and calculations reuse existing outputs, so rerunning the commands continues from saved results.

| Path | Contents |
| --- | --- |
| `build/<suite>/<snapshot>/` | Rugix Bakery build output, including filesystem images and tar archives. |
| `results/base-sizes/` | Uncompressed image sizes and complete-image XZ sizes. |
| `results/xdelta/` | Binary patch sizes for each update pair. |
| `results/block-diffing/` | Block reuse estimates by model and update pair. |
| `results/deltar/` | Deltar estimates, including reconstruction-plan and data sizes. |

Build outputs and generated results are ignored by Git.

| Environment Variable | Purpose |
| --- | --- |
| `BENCHMARK_JOBS` | Number of parallel simulations; defaults to four. |
| `RUGIX_BUNDLER` | Path to a Rugix Bundler executable. Otherwise, the script uses `rugix-bundler` from `PATH`, then `.cache/bin/rugix-bundler`. |
| `DOCKER` | Container engine for Rugix Bakery image builds; defaults to `docker`. |
| `RUGIX_BAKERY_IMAGE` | Rugix Bakery container image; use the pinned digest in the reproduction commands. |
