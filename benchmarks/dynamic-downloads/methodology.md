# Native Dynamic Delta Update Methodology

These benchmarks install Rugix Ctrl and RAUC bundles from an Nginx HTTP server into disposable KVM virtual machines. Linux traffic control applies bandwidth and packet delay on a private link inside each guest. See the [benchmark results](README.md) for measurements and findings.

For machine requirements and commands, see [Reproduce the Measurements](README.md#reproduce-the-measurements).

## Corpus and Native Installers

Dynamic delta updates reconstruct a target filesystem by reusing matching data from an existing filesystem and fetching missing data from a complete bundle. These benchmarks install ARM64 Debian filesystem images as data using native x86-64 installers in a KVM guest.

| Workload | Source | Target |
| --- | --- | --- |
| Monthly | Bookworm, May 2025 | Bookworm, June 2025 |
| Annual | Bookworm, June 2024 | Bookworm, June 2025 |
| Major Upgrade | Bullseye, May 2025 | Bookworm, June 2025 |

The plans record exact Debian snapshot timestamps. Rugix Bakery uses a pinned container digest and a fixed source date. The target payload is byte-identical across bundle formats. Both installers use 4 GiB raw source and target slots. Each source slot contains its selected old filesystem followed by zeros; each target starts blank. Reuse indices are prepared before timing, including RAUC indices for both slots.

Both Rugix Ctrl versions use the same pinned Nix compiler profile. The release build is v1.3.0 at `48fc40d3d903730781f3dc4bf671873d2308573a`. The build with concurrent HTTP fetching is `b82749ff34ee8668fb3e53322af039a083e8bf69`, labeled “Rugix Ctrl concurrent fetcher” in the results. The records in `results/2026-10` include executable hashes and input hashes. Source-file paths in the provenance manifests refer to the [measurement source tree](https://github.com/rugix/rugix-benchmarks/tree/390c70f0a7676b541d348924d6fe6414e0d54d8d).

Rugix Ctrl uses Casync content-defined chunks with a nominal size of 64 KiB (Casync64), deduplication, and per-chunk XZ compression. RAUC 1.15.2 uses a signed verity bundle with `block-hash-index`, 4 KiB reuse blocks, and 64 KiB XZ SquashFS compression blocks. RAUC documents 64 KiB as an example for reducing compression-block download overhead. See [RAUC adaptive updates](https://rauc.readthedocs.io/en/latest/advanced.html#block-based-adaptive-update-block-hash-index).

The main comparison uses plain HTTP/1.1 for Rugix Ctrl and RAUC. Separate RAUC controls use verified TLS with HTTP/1.1 and HTTP/2. Nginx logs the negotiated protocol for every request, and the runner checks it. These controls separate protocol effects from the installer comparison. The calibration plan uses Rugix Ctrl with nominal 16 KiB Casync chunks (Casync16) and RAUC with 32 KiB compression groups to compare measured bytes with the corresponding byte models.

## Network Conditions

A veth pair connects the installer to an Nginx network namespace. Benchmark traffic stays inside this link. SSH management traffic uses a separate interface, and a test transfer must leave benchmark counters unchanged.

Both directions have a 20 MiB/s bandwidth limit. Incoming packets are redirected to an IFB device with a TBF bandwidth shaper and a child netem queue. Each direction receives half the requested round-trip delay: 0, 5, or 20 ms. The added RTTs are therefore 0, 10, and 40 ms. MTU is 1500, and segmentation/coalescing offloads are disabled. No loss or jitter is deliberately added.

Every sample runs a ten-packet ping and a four-stream reverse iperf3 check before installation. The runner retains measured RTT distributions, actual throughput, queue settings, and offload settings. It rejects unexpected delay or bandwidth and rejects queue, interface, or capture drops during installation.

## Repetitions and Timing

The main plan has 225 installs: three workloads, three RTTs, five installer configurations, and five repetitions. Each sample boots a fresh guest with four virtual CPUs and 8 GiB RAM. Within a workload/RTT block, candidate order rotates across repetitions, so every candidate occupies every position once. A fixed seed shuffles block order.

Before timing, the runner drops guest caches, then reads the complete source payload, served bundle, and reuse indices. This controls cache state and warms the host backing files through the same guest reads. It verifies the source hash and updater binary hash outside the timer.

Elapsed time covers the native install command, including range fetching, decompression, data reuse, reconstruction, native verification, writes, and index persistence. It excludes VM boot, fixture preparation, network calibration, cache warmup, packet retrieval, and independent final hashing. No reboot is timed. RAUC installs a raw data slot and Rugix Ctrl installs the matching named slot.

Tables report medians, interquartile ranges, and five samples per condition. Machine-readable summaries also retain minima and maxima. Release/pipeline speedups pair measurements from the same repetition, workload, and RTT.

## Traffic Accounting and Verification

The suite captures outbound frames once at each veth endpoint, before receiver-side IFB reinjection. Capture frame bytes and packet counts must exactly match interface transmit counters and the opposite endpoint's receive counters. Both directions include Ethernet, IP, TCP, TLS or HTTP headers, acknowledgments, and retransmissions. These are veth Ethernet frame bytes; physical Ethernet preambles, interpacket gaps, and frame checksums are not represented.

Plain HTTP bodies are decoded from unique captured TCP sequence data using h11. This retains bytes from responses an installer intentionally stops reading early. Nginx bytes written are retained separately because they can exceed bytes delivered before a connection closes. TLS body counts are reconciled between Nginx and RAUC's native download counters. Encrypted captures still measure full interface traffic.

Every successful sample independently hashes the reconstructed target and compares it with the packaged payload. The runner also checks the HTTP protocol, response status, connection counts, finished delivery queues, zero packet loss, and RAUC's native request/body counters before accepting a sample.

An independent matcher hashes target blocks at 4 KiB boundaries and classifies them as zero data, reusable data from the already written target prefix, reusable source-image data, or data requiring a bundle read. The runner compares these counts with RAUC's provider counters for every install. The published reuse table reports the matching counts and number of checked installs.

## Interpreting the Results

Results describe warm-cache installation on the specified VM and Debian image pairs. CPU, storage, cache state, and network conditions affect installation time.

The simulator's 768-byte per-group overhead estimate is compared with delivered body bytes, download-direction interface bytes, and complete bidirectional interface bytes separately. Apply correction factors to the measured installer, encoding, and traffic metric. Casync64 and Casync16 have separate measurements.

Each image pair provides one workload with five repeated timings per condition. The calibration covers two Bookworm minor updates and one Bullseye-to-Bookworm upgrade.

## Run Management

### Stored Files

Preparation builds pinned tools, four Debian filesystem images, four bundle variants, and three source fixtures, and computes theoretical download sizes. Build work and measurement run separately so compilation and simulations do not compete with timed installations.

Campaign records are stored under the `--output` directory, which defaults to `.cache/paper` for the main plan. Each campaign has a `runs/` directory containing packet captures and installer logs. Successful runs discard disposable VM disks after saving evidence; failed runs retain their disks and logs.

The report command exports samples, tables, correction factors, provenance, and figures to `results/2026-10/`. It requires both complete campaigns, selected with `--paper` and `--calibration`; their default paths are `.cache/paper` and `.cache/calculator`.

### Resume or Retry a Campaign

Rerun a `run` command with the same plan and output directory to resume an interrupted campaign. The runner verifies the plan, measurement code, tools, bundles, and fixtures before reusing completed records. Select a new output directory when those inputs change.

Before retrying a failed install, move its run directory outside the campaign's `runs/` directory, then rerun the campaign command. For example, if `monthly-rtt10-rugix-pipeline-0` failed:

```sh
mkdir -p .cache/failed-runs
mv .cache/paper/runs/monthly-rtt10-rugix-pipeline-0 .cache/failed-runs/
uv run --locked benchmark run --plan plans/paper.json --output .cache/paper
```

To run only the next pending install, add `--limit 1` to the command. A completed campaign has no pending installs.
