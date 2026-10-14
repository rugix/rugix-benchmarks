# Rugix Benchmarks

Reproducible benchmarks for Rugix and related update tools. Each benchmark has its own README with its purpose, inputs, reproduction commands, and interpretation of results.

## Benchmarks

| Benchmark | What It Measures |
| --- | --- |
| [Delta-Update Byte Simulations](delta-updates/README.md) | Theoretical download sizes across two years of Debian images, comparing whole-image compression, xdelta, and block reuse. |
| [Native Adaptive-Update Installations](adaptive-downloads/README.md) | Installation time and actual network traffic for Rugix and RAUC at different latencies, including repeated measurements and download-size model calibration. |

The [October 2026 native results](adaptive-downloads/README.md#findings) include 255 verified installations. At 40 ms added round-trip latency, the monthly Rugix update fell from a median of 457.6 seconds with v1.3.0 to 31.0 seconds with the new fetching pipeline.

## Repository Layout

Benchmark-specific files live in their respective directories:

- `delta-updates/`: byte simulator, image recipes, and locally generated simulation outputs.
- `adaptive-downloads/`: native VM recipes, fixtures, plans, methodology, and published results.

Shared tooling lives at the repository root:

- `nix/`: pinned toolchain and native build dependencies.
- `src/rugix_benchmarks/`: preparation, measurement, verification, and reporting helpers.
- `schemas/`: Sidex definitions for plans and measurement records.
- `tests/`: regression checks for shared measurement code.

Local images, builds, packet captures, and native logs use ignored cache directories. Published measurement records, figures, and provenance stay with their benchmark.

## Getting Started

Clone this repository, then run the setup and reproduction commands in the selected benchmark's README from the working directory it specifies. The shared Python tools use [uv](https://docs.astral.sh/uv/), and the pinned toolchain uses Nix:

```sh
nix develop path:./nix
uv sync --locked
```

The native installation benchmark requires Linux with KVM and Podman. The byte simulator has its own corpus and compute requirements; consult its README before starting a full run.

## Adding a Benchmark

Create a directory with a README that explains what the benchmark measures, how to reproduce it, and how to interpret its results. Keep its plans, fixtures, and published results in that directory. Record tool versions, input hashes, measured conditions, and every repeated sample with the results. Reuse the shared toolchain and helpers where applicable.

## License

Benchmark code is available under either the [Apache-2.0](LICENSE-APACHE) or [MIT](LICENSE-MIT) license. External tools retain their own licenses.
