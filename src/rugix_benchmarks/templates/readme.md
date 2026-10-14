# Rugix Benchmarks

Reproducible delta-update benchmarks for Rugix and RAUC. [Byte simulations](delta-updates/README.md) estimate download sizes across two years of Debian images. [Native installation benchmarks](adaptive-downloads/README.md) test selected image pairs with real bundles, Linux network shaping, and measured interface traffic.

## Findings

At 40 ms added round-trip latency, the monthly pipeline install had a median of **{monthly_new40:.1f} seconds**, compared with **{monthly_old40:.1f} seconds** for Rugix v1.3.0. Its median paired speedup was **{monthly_speedup40:.1f}×** across five repetitions.

At 10 ms RTT, monthly connection counts fell from {monthly_old_connections:.0f} to {monthly_new_connections:.0f}. The pipeline delivered {monthly_body_mib:.2f} MiB of HTTP bodies and transferred {monthly_total_mib:.2f} MiB across the link. RAUC HTTP/1.1 delivered {monthly_rauc_body_mib:.2f} MiB and transferred {monthly_rauc_total_mib:.2f} MiB.

RAUC's monthly HTTP/2 median at 40 ms RTT was {monthly_rauc_h2_40:.1f} seconds; verified TLS HTTP/1.1 took {monthly_rauc_h1_40:.1f} seconds. All protocol results remain in the tables, including repeated measurements at zero latency.

![Verified installation time](results/2026-10/installation-time.svg)

Lines show medians, error bars show interquartile ranges, and faint dots show individual installs. Monthly pipeline times at 40 ms ranged from {monthly_new40_min:.1f} to {monthly_new40_max:.1f} seconds. All five verified results are retained.

Download savings depend on bundle compression and access patterns. The complete Rugix and RAUC bundles are {rugix_bundle_mib:.2f} and {rauc_bundle_mib:.2f} MiB. A whole-image XZ stream is {baseline_mib:.2f} MiB. The size figure retains that compression-only reference separately from native traffic.

For the major upgrade at 10 ms RTT, RAUC HTTP/1.1 delivered {major_rauc_body_mib:.2f} MiB, {major_rauc_bundle_ratio:.2f} times its complete bundle size. Repeated and overlapping reads count each time. Complete-bundle sizes are byte references; full-download installation times were not measured.

![Delivered bodies and complete interface traffic](results/2026-10/download-size.svg)

The original 768-byte per-group model gives configuration-dependent errors. For the monthly Casync64 pipeline case, body and full-link factors are {monthly_body_factor:.3f} and {monthly_total_factor:.3f}; RAUC 64 KiB factors are {monthly_rauc_body_factor:.3f} and {monthly_rauc_total_factor:.3f}. Separate Casync16 and RAUC 32 KiB measurements support a [provisional calculator calibration](results/2026-10/calculator.md).

The [Faster Delta Updates article](https://rugix.org/blog/faster-delta-updates) presents the design and interpretation. Its source lives in Rugix Docs.

## Measured Conditions

The comparison uses Rugix v1.3.0 at `48fc40d3d903730781f3dc4bf671873d2308573a`, the pipeline PR at `b82749ff34ee8668fb3e53322af039a083e8bf69`, and RAUC 1.15.2. Both Rugix revisions are built with the same pinned compiler. Every tool reconstructs the same 1411.27 MiB payload.

The main campaign contains 225 verified native installs: three workloads, three RTTs, five configurations, and five repetitions. A separate 30-install campaign measures the calculator's Casync16 and RAUC 32 KiB configurations. Earlier exploratory smokes and pilots are excluded.

Each sample uses a fresh guest with four virtual CPUs, 8 GiB RAM, a blank target, prepared indices, and consistent warm caches. Nginx serves bundles over a private veth link. Receiver-side Linux TBF/netem applies 20 MiB/s in each direction and 0, 10, or 40 ms added RTT. The management OS is Debian Bookworm with kernel 6.1.0-35-amd64.

Timing covers the native install command, including fetching, decoding, verification, reconstruction, writes, and index persistence. It excludes boot, preparation, calibration, cache warmup, independent final hashing, and reboot. Actual RTT and throughput are checked before every install. Payload hashes, HTTP protocol, and exact packet/interface counter agreement are required for acceptance.

{tables}

## Raw Data and Provenance

- [Every accepted sample, CSV](results/2026-10/samples.csv)
- [Main sample records](results/2026-10/paper-samples.json) and [plan](results/2026-10/paper-plan.json)
- [Calculator samples](results/2026-10/calculator-samples.json) and [plan](results/2026-10/calculator-plan.json)
- [Main provenance](results/2026-10/paper-provenance.json) and [calculator provenance](results/2026-10/calculator-provenance.json)
- [Per-workload correction factors](results/2026-10/corrections.json) and [independently checked RAUC reuse](results/2026-10/reuse.json)
- [Theoretical estimates](results/2026-10/theory) and [timing summaries](results/2026-10/summary.json)

Packet captures and full native logs remain in the local campaign cache. Plans, samples, correction factors, and reuse statistics have [Sidex schemas](schemas/benchmark.sidex). Figures are available as SVG, PDF, and PNG beside the sample data.

## Reproduce

Use x86-64 Linux with writable `/dev/kvm`, Nix, and Podman. See the [native benchmark methodology](adaptive-downloads/README.md) for cache controls, timing boundaries, traffic accounting, and resource requirements.

```sh
nix develop path:./nix
uv sync --locked
uv run --locked rugix-benchmarks prepare
uv run --locked rugix-benchmarks smoke
uv run --locked rugix-benchmarks run --plan plans/paper.json --output .cache/paper
uv run --locked rugix-benchmarks run --plan plans/calculator.json --output .cache/calculator
uv run --locked rugix-benchmarks report
```

Successful results resume with immutable input checks. Failed evidence is retained. The reporting command regenerates the tables, figures, README, calculator proposal, and `results/2026-10/article-data.json` from complete campaigns. Prose templates are in `src/rugix_benchmarks/templates`.

The article is maintained in Rugix Docs. To refresh its interactive graphs in an adjacent checkout:

```sh
cp results/2026-10/article-data.json ../rugix-docs/src/components/native-delta-data.json
```

## Scope

Selected ARM64 filesystems are installed as data in a native x86-64 VM and are not booted. Blank targets keep the comparison aligned with the simulator's single source image; they exclude recovery from a partial install and extra reuse from another older slot. These measurements describe this VM, kernel, network, and selected corpus.

Five repetitions quantify variation within one image pair. They do not create five independent workloads. The calculator calibration covers two Bookworm minor-update pairs and one Bullseye-to-Bookworm upgrade; it does not replace the original two-year corpus. The calculator remains unchanged pending calibration review.

## License

Benchmark code is available under either the Apache-2.0 or MIT license. External tools retain their own licenses.
