# Rugix Benchmarks

This repository contains reproducible benchmarks for comparing Linux image update techniques, estimating download sizes, and measuring Rugix Ctrl and RAUC installation performance. Each benchmark directory contains its inputs, tools, and reproduction instructions.

| Benchmark | What It Measures |
| --- | --- |
| [Delta-Update Byte Simulations](benchmarks/delta-updates/README.md) | Estimated download sizes for several delta update techniques across two years of Debian images. |
| [Dynamic Delta Update Performance](benchmarks/dynamic-downloads/README.md) | Installation time and network traffic for Rugix Ctrl and RAUC at different network latencies, with repeated measurements and published results. |

## Download Size Estimates

The byte simulations cover two years of ARM64 Debian Bookworm and Bullseye images. For updates within a Debian release, selected techniques produced these estimated download sizes:

| Technique | Monthly Updates | Annual Updates |
| --- | ---: | ---: |
| Binary patches with Xdelta | 12.0% | 27.7% |
| Fixed 4 KiB blocks, compressed in 64 KiB groups | 26.6% | 67.4% |
| Content-defined blocks, nominal 16 KiB | 22.9% | 64.3% |
| File-content reuse with Deltar | 20.3% | 57.1% |

Values are percentages of complete-image XZ download sizes, with equal weight for Bookworm and Bullseye; lower values use fewer bytes. For the sampled Bullseye-to-Bookworm upgrades, all four delta models exceeded the size of a complete-image XZ download. See the [simulation results and assumptions](benchmarks/delta-updates/README.md#results) and [published analysis](https://rugix.org/blog/efficient-delta-updates/) for details.

## Faster Dynamic Delta Updates

Dynamic delta updates reuse data from an installed image to reduce downloads. Across three selected Debian update pairs, Rugix Ctrl's concurrent fetcher achieved **median installation speedups of about 14–31× over both Rugix Ctrl 1.3.0 and RAUC 1.15.2** using HTTP/1.1 on a 20 MiB/s link with 40 ms of added round-trip delay. Each condition was measured five times.

For the monthly Bookworm update, median installation times were:

| Installer | Median Installation Time |
| --- | ---: |
| Rugix Ctrl 1.3.0 | 457.6 s |
| RAUC 1.15.2 | 440.5 s |
| Rugix Ctrl concurrent fetcher | 31.0 s |

Rugix Ctrl 1.3.0 and RAUC had similar median installation times at 40 ms added delay across all three update pairs. The new pipeline substantially improves on both. At zero added delay, it showed no consistent speedup over Rugix Ctrl 1.3.0. See the [complete comparison](benchmarks/dynamic-downloads/README.md) for graphs, traffic measurements, and reproduction instructions.

## License

Benchmark code is available under either the [Apache-2.0](LICENSE-APACHE) or [MIT](LICENSE-MIT) license. External tools retain their own licenses.
