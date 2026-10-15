# Dynamic Delta Update Performance

Dynamic delta updates reconstruct a new filesystem image by reusing data already available on a device and downloading the missing parts of an update bundle. This benchmark compares installation time and network traffic for Rugix Ctrl 1.3.0, a Rugix Ctrl build with concurrent HTTP fetching, and RAUC 1.15.2.

For a monthly Debian Bookworm update at 40 ms of added round-trip delay, median installation times were **{monthly_old40:.1f} seconds with Rugix Ctrl 1.3.0**, **{monthly_rauc40:.1f} seconds with RAUC 1.15.2**, and **{monthly_new40:.1f} seconds with the concurrent fetcher**. These medians come from five installations per configuration on a 20 MiB/s link. At zero added delay, the measurements show no consistent speedup over Rugix Ctrl 1.3.0 across the three tested update pairs.

Read the [results](#results), [reproduce the measurements](#reproduce-the-measurements), or inspect the [measurement data](#data-and-provenance).

## Experiment

Each workload installs the same 1411.27 MiB target filesystem image from a different source image:

| Workload | Source Image | Target Image |
| --- | --- | --- |
| Monthly | Debian Bookworm, May 2025 | Debian Bookworm, June 2025 |
| Annual | Debian Bookworm, June 2024 | Debian Bookworm, June 2025 |
| Major | Debian Bullseye, May 2025 | Debian Bookworm, June 2025 |

ARM64 filesystem images are installed as data by x86-64 installers in KVM guests. Each guest has four virtual CPUs, 8 GiB RAM, a blank target slot, prepared reuse indices, and warm caches. Nginx serves bundles over a private link limited to 20 MiB/s in each direction, with 0, 10, or 40 ms of added round-trip time (RTT).

| Installer Label | Measured Version |
| --- | --- |
| Rugix Ctrl 1.3.0 | Release revision `48fc40d3d903730781f3dc4bf671873d2308573a` |
| Rugix Ctrl concurrent fetcher | Prerelease revision `b82749ff34ee8668fb3e53322af039a083e8bf69` |
| RAUC | 1.15.2 |

Both Rugix Ctrl builds use the same pinned compiler and plain HTTP/1.1. RAUC is measured with plain HTTP/1.1, TLS with HTTP/1.1, and TLS with HTTP/2. Five repetitions of every workload, latency, and installer configuration give 225 main measurements. Each speedup is an installation time with Rugix Ctrl 1.3.0 or RAUC divided by the time with the concurrent fetcher for the same repetition, workload, and latency. Reported speedups are medians of those five ratios.

Rugix Ctrl uses Casync content-defined chunking, which places chunk boundaries according to data content. Its nominal 64 KiB configuration is labeled **Casync64**, and each chunk is compressed individually with XZ. RAUC's `block-hash-index` adaptive update method reuses fixed 4 KiB blocks and retrieves missing data from 64 KiB XZ compression groups in a SquashFS bundle. A compression group contains blocks compressed together, so retrieving one block can require downloading adjacent data.

Installation time covers the install command, including fetching, decompression, verification, reconstruction, writes, and index persistence. VM boot, fixture preparation, network calibration, cache warmup, independent final hashing, and reboot are excluded. Every recorded install passed a target-image hash check and reconciliation of packet captures with interface counters.

| Traffic Metric | Definition |
| --- | --- |
| Body | Delivered HTTP response-body bytes, including bundle metadata and repeated reads. |
| Download | All server-to-client network-interface bytes, including protocol overhead. |
| Total | Network-interface bytes in both directions, including requests, acknowledgments, and retransmissions. |

The [methodology](methodology.md) specifies image construction, network shaping, timing, and verification.

## Results

### Installation Time

At 40 ms added RTT, median speedups across the three workloads ranged from **{speedup40_low:.1f}× to {speedup40_high:.1f}× over Rugix Ctrl 1.3.0** and **{rauc_speedup40_low:.1f}× to {rauc_speedup40_high:.1f}× over RAUC**. Rugix Ctrl 1.3.0 and RAUC had similar median installation times under these conditions; the concurrent fetcher substantially improves on both.

The concurrent fetcher combines adjacent ranges, reuses connections, and keeps several requests in flight. For the monthly update at 10 ms added RTT, it used {monthly_new_connections:.0f} connections, compared with {monthly_old_connections:.0f} for Rugix Ctrl 1.3.0.

![Installation time by workload and added round-trip time](results/2026-10/installation-time.svg)

Lines show medians, error bars cover the middle 50% of measurements, and dots show individual installs. Monthly times with the concurrent fetcher at 40 ms ranged from {monthly_new40_min:.1f} to {monthly_new40_max:.1f} seconds.

### Network Traffic

For the monthly update at 10 ms added RTT, the concurrent fetcher transferred **{monthly_total_mib:.2f} MiB** in both directions, compared with **{monthly_rauc_total_mib:.2f} MiB** for RAUC over HTTP/1.1, a reduction of **{monthly_traffic_reduction_pct:.1f}%**. Their delivered response bodies were {monthly_body_mib:.2f} and {monthly_rauc_body_mib:.2f} MiB, respectively.

![Delivered HTTP bodies and bidirectional interface traffic at 10 ms added RTT](results/2026-10/download-size.svg)

Bundle compression and access patterns affect the savings. The complete Rugix Ctrl and RAUC bundles are {rugix_bundle_mib:.2f} and {rauc_bundle_mib:.2f} MiB; compressing the target as a single XZ stream produces {baseline_mib:.2f} MiB, shown as a size reference in the figure. Full-download installation times were not measured.

For the major upgrade, RAUC delivered {major_rauc_body_mib:.2f} MiB of response bodies at 10 ms added RTT, or {major_rauc_bundle_ratio:.2f} times its bundle size. Response-body counts include repeated and overlapping reads.

### Accuracy of Download Size Estimates

The [byte simulations](../delta-updates/README.md) estimate compressed data and indices with 768 bytes of transfer overhead per downloaded compression group. A correction factor divides measured bytes by that estimate: values above one indicate an underestimate, and values below one indicate an overestimate.

For the monthly Casync64 update, the concurrent fetcher's body and total-traffic factors are {monthly_body_factor:.3f} and {monthly_total_factor:.3f}. RAUC's corresponding factors with 64 KiB compression groups are {monthly_rauc_body_factor:.3f} and {monthly_rauc_total_factor:.3f}.

A separate 30-install calibration measures the same Rugix Ctrl concurrent fetcher with nominal 16 KiB chunks (**Casync16**) and RAUC 1.15.2 with 32 KiB compression groups. Both use plain HTTP/1.1. The [calibration report](results/2026-10/calculator.md) provides factors for the savings calculator's models and explains their applicability.

## Reproduce the Measurements

Use x86-64 Linux with writable `/dev/kvm`, Nix with flakes enabled, and Podman. Allow at least 12 GiB of free RAM and about 150 GiB of disk space for images, builds, and captures. Run one campaign at a time on an otherwise idle host.

From `benchmarks/dynamic-downloads`, prepare the inputs, check the installers, run both measurement plans, and generate the report:

```sh
nix develop path:./nix
uv sync --locked
uv run --locked benchmark prepare
uv run --locked benchmark smoke
uv run --locked benchmark run --plan plans/paper.json --output .cache/paper
uv run --locked benchmark run --plan plans/calculator.json --output .cache/calculator
uv run --locked benchmark report
```

A successful report confirms 225 main and 30 calibration installs and writes results to `results/2026-10/`. It regenerates this README, measurement tables, figures, and the calibration report. See [Run Management](methodology.md#run-management) for resuming interrupted campaigns and handling failed runs.

## Detailed Results

Installation times are medians with first and third quartiles in brackets. Traffic tables show medians of five measurements per condition.

{tables}

## Data and Provenance

| Data | Contents |
| --- | --- |
| [Samples, CSV](results/2026-10/samples.csv) | All 255 recorded installations. |
| [Main samples](results/2026-10/paper-samples.json) and [plan](results/2026-10/paper-plan.json) | Installation-time and traffic measurements for the five main configurations. |
| [Calibration samples](results/2026-10/calculator-samples.json) and [plan](results/2026-10/calculator-plan.json) | Casync16 and RAUC 32 KiB measurements. |
| [Main provenance](results/2026-10/paper-provenance.json) and [calibration provenance](results/2026-10/calculator-provenance.json) | Input identities, software versions, hashes, and recorded environment. |
| [Correction factors](results/2026-10/corrections.json) | Measured-to-modeled byte ratios. |
| [RAUC reuse](results/2026-10/reuse.json) | Independently checked block-reuse counts. |
| [Theoretical estimates](results/2026-10/theory/) | Compressed sizes from the byte models. |
| [Timing summaries](results/2026-10/summary.json) and [tables](results/2026-10/tables.md) | Timing statistics and complete result tables. |

Packet captures and installer logs are written to each local campaign's `runs/` directory. The figures are available as SVG, PDF, and PNG in `results/2026-10/`; [Sidex definitions](schemas/benchmark.sidex) describe the machine-readable records.

## Scope

The measurements cover three image pairs on the specified VM, kernel, network, and warm-cache setup. Each target starts blank, so partial-install recovery is outside the measured workload. Five repetitions characterize variation within each image pair; the calibration covers two Bookworm minor updates and one Bullseye-to-Bookworm upgrade.

## License

Benchmark code is available under either the Apache-2.0 or MIT license. External tools retain their own licenses.
