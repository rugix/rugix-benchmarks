# Native Adaptive-Update Methodology

These benchmarks install real Rugix and RAUC bundles into disposable KVM virtual machines. Linux traffic control applies bandwidth and packet delay on a private link inside each guest. Nginx serves bundles without application-level delays or simulated request costs. See the [benchmark results](README.md) for the repeated measurements and findings.

## Reproduce the Measurements

Use an x86-64 Linux machine with writable `/dev/kvm`, Nix with flakes enabled, and Podman. Allow at least 12 GiB of free RAM and about 150 GiB of disk space for images, fixtures, packet captures, and native build dependencies. Run one campaign at a time on an otherwise idle host.

Run from `benchmarks/adaptive-downloads`. All Python dependencies, recipes, fixtures, plans, and reporting code are local to this experiment. The generated Python data models are included, so reproducing the experiment does not require Sidex tooling:

```sh
nix develop path:./nix
uv sync --locked
uv run --locked benchmark prepare
uv run --locked benchmark smoke
uv run --locked benchmark run --plan plans/paper.json --output .cache/paper
uv run --locked benchmark run --plan plans/calculator.json --output .cache/calculator
uv run --locked benchmark report
```

Preparation builds pinned tools, four historical Debian filesystems, four bundle variants, and three source fixtures. It also runs the original byte simulator. Preparation and measurement run separately so builds and simulations do not compete with timed installs.

Output remains in `.cache`. The reporting command exports checked samples, tables, correction factors, provenance, and publication figures into `results/2026-10`. Packet captures and full native logs remain in each campaign's `runs` directory. Successful runs discard disposable VM disks after saving evidence. Failed runs retain their VM disks and logs.

Rerun the same `run` command to resume an interrupted campaign. It checks the plan, measurement code, tools, bundle identities, and fixture identities. It recovers completed per-run records if interruption occurred before the aggregate was saved. Changed inputs require a new output directory. Published samples and provenance retain their original paths and hashes; the original campaign layout and measurement code are available in [commit `390c70f`](https://github.com/rugix/rugix-benchmarks/tree/390c70f0a7676b541d348924d6fe6414e0d54d8d). Preserve a failed run under a separate diagnostics directory before retrying; the runner does not overwrite it.

To inspect a campaign in small steps:

```sh
uv run --locked benchmark run --plan plans/paper.json --output .cache/paper --limit 1
```

## Corpus and Native Installers

Adaptive updates reconstruct a target filesystem by reusing matching data from an existing filesystem and fetching missing data from a complete bundle. The source corpus is the same ARM64 Debian corpus used by the original delta-update simulations. ARM64 filesystems are installed as opaque payloads in an x86-64 native updater VM. They are not booted.

| Workload | Source | Target |
| --- | --- | --- |
| Monthly | Bookworm, May 2025 | Bookworm, June 2025 |
| Annual | Bookworm, June 2024 | Bookworm, June 2025 |
| Major Upgrade | Bullseye, May 2025 | Bookworm, June 2025 |

The plans record exact Debian snapshot timestamps. Bakery uses a pinned container digest and a fixed source date. The target payload is byte-identical across bundle formats. Both installers use 4 GiB raw source and target slots. Each source slot contains its selected old filesystem followed by zeros; each target starts blank. Reuse indices are prepared before timing, including RAUC indices for both slots.

Both Rugix versions are rebuilt with the same pinned Nix compiler profile. The release comparison uses v1.3.0 at `48fc40d3d903730781f3dc4bf671873d2308573a`. The pipeline implementation uses PR revision `b82749ff34ee8668fb3e53322af039a083e8bf69`. The suite records native executable hashes. This measures the selected source revisions with matched build tooling.

Rugix uses Casync64 content-defined chunks, deduplication, and per-chunk XZ compression. RAUC 1.15.2 uses a signed verity bundle with `block-hash-index`, 4 KiB reuse blocks, and 64 KiB XZ SquashFS compression blocks. RAUC documents 64 KiB as an example for reducing compression-block download overhead. See [RAUC adaptive updates](https://rauc.readthedocs.io/en/latest/advanced.html#block-based-adaptive-update-block-hash-index).

The main comparison uses plain HTTP/1.1 for Rugix and RAUC. Separate RAUC controls use verified TLS with HTTP/1.1 and HTTP/2. Nginx logs the negotiated protocol for every request, and the runner checks it. These controls separate protocol effects from the installer comparison. The supplemental calculator plan uses Rugix Casync16 and RAUC 32 KiB compression groups, matching the current calculator's theoretical configurations.

## Network Conditions

A veth pair connects the installer to an Nginx network namespace. Benchmark traffic stays inside this link. SSH management traffic uses a separate interface, and a test transfer must leave benchmark counters unchanged.

Both directions have a 20 MiB/s bandwidth limit. Incoming packets are redirected to an IFB device with a TBF bandwidth shaper and a child netem queue. Each direction receives half the requested round-trip delay: 0, 5, or 20 ms. The added RTTs are therefore 0, 10, and 40 ms. MTU is 1500, and segmentation/coalescing offloads are disabled. No loss or jitter is deliberately added.

Every sample runs a ten-packet ping and a four-stream reverse iperf3 check before installation. The runner retains measured RTT distributions, actual throughput, queue settings, and offload settings. It rejects unexpected delay or bandwidth and rejects queue, interface, or capture drops during installation.

RTT represents packet delay between client and origin. It is not a fixed delay inserted once per HTTP request. Congestion control, connection establishment, acknowledgment traffic, and range requests use the normal Linux networking stack.

## Repetitions and Timing

The main plan has 225 installs: three workloads, three RTTs, five installer configurations, and five repetitions. Each sample boots a fresh guest with four virtual CPUs and 8 GiB RAM. Within a workload/RTT block, candidate order rotates across repetitions, so every candidate occupies every position once. A fixed seed shuffles block order.

Before timing, the runner drops guest caches, then reads the complete source payload, served bundle, and reuse indices. This controls cache state and warms the host backing files through the same guest reads. It verifies the source hash and updater binary hash outside the timer.

Elapsed time covers the native install command, including range fetching, decompression, data reuse, reconstruction, native verification, writes, and index persistence. It excludes VM boot, fixture preparation, network calibration, cache warmup, packet retrieval, and independent final hashing. No reboot is timed. RAUC installs a raw data slot and Rugix installs the matching named slot.

Tables report medians, interquartile ranges, and five samples per condition. Machine-readable summaries also retain minima and maxima. Release/pipeline speedups pair measurements from the same repetition, workload, and RTT. Earlier exploratory pilot runs are excluded.

## Traffic Accounting and Verification

The suite captures outbound frames once at each veth endpoint, before receiver-side IFB reinjection. Capture frame bytes and packet counts must exactly match interface transmit counters and the opposite endpoint's receive counters. Both directions include Ethernet, IP, TCP, TLS or HTTP headers, acknowledgments, and retransmissions. These are veth Ethernet frame bytes; physical Ethernet preambles, interpacket gaps, and frame checksums are not represented.

Plain HTTP bodies are decoded from unique captured TCP sequence data using h11. This retains bytes from responses an installer intentionally stops reading early. Nginx bytes written are retained separately because they can exceed bytes delivered before a connection closes. TLS body counts are reconciled between Nginx and RAUC's native download counters. Encrypted captures still measure full interface traffic.

Every successful sample independently hashes the reconstructed target. It must match the packaged payload. The runner also checks actual HTTP protocol, response status, connection counts, finished delivery queues, zero packet loss, and RAUC's native request/body counters. These checks run before a sample is accepted.

## Interpreting the Results

These measurements describe warm-cache native installation on this VM and selected corpus. They do not characterize flash endurance, slow embedded CPUs, first-use index generation, reboot time, lossy mobile networks, or a remote server's concurrency limits. Fresh blank targets intentionally exclude partial-update recovery savings.

The simulator's 768-byte per-group allowance is compared with delivered body bytes, download-direction link bytes, and complete bidirectional link bytes separately. Correction factors apply to a particular encoding and byte definition. Casync64 measurements cannot directly correct Casync16 estimates. A native Rugix measurement also does not establish the overhead of a separate casync implementation.

Five repeated installs characterize timing variation for one image pair. They do not create five independent workloads. The selected two Bookworm update pairs and one Bullseye-to-Bookworm upgrade support a provisional calibration; they do not replace the original two-year corpus.
