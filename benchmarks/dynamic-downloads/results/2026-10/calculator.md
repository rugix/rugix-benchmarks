# Savings Calculator Calibration

These factors compare measured transfer sizes with the [byte model](../../../delta-updates/README.md) used by Rugix's savings calculator.

## Measured Configurations

The [calibration plan](../../plans/calculator.json) measures Rugix Ctrl's concurrent fetcher at revision `b82749ff34ee8668fb3e53322af039a083e8bf69` with nominal 16 KiB Casync chunks (Casync16), and RAUC 1.15.2 with 32 KiB XZ compression groups. Both use plain HTTP/1.1. The corresponding byte models are `block-based-casync-16-768` and `block-based-fixed-4-768-32768`, respectively. Five installs at zero added RTT cover each monthly, annual, and major-upgrade pair.

| Update | Native Configuration | Model, MiB | Body Factor | Download Factor | Total Factor |
| --- | --- | ---: | ---: | ---: | ---: |
| Monthly | Rugix Ctrl Casync16 | 170.14 | 0.895 | 0.942 | 0.956 |
| Monthly | RAUC 32 KiB | 180.23 | 1.453 | 1.553 | 1.579 |
| Annual | Rugix Ctrl Casync16 | 221.49 | 0.887 | 0.932 | 0.945 |
| Annual | RAUC 32 KiB | 226.11 | 1.436 | 1.537 | 1.563 |
| Major | Rugix Ctrl Casync16 | 369.67 | 0.883 | 0.924 | 0.939 |
| Major | RAUC 32 KiB | 356.86 | 1.385 | 1.482 | 1.507 |

Each factor is the measured median byte count divided by the model's compressed size estimate, which includes 768 bytes of overhead per fetched compression group. Multiply that estimate by the selected factor to obtain a corrected byte count. A factor below one means the model overestimates that metric.

## Keep Byte Definitions Separate

- **Body factor:** delivered HTTP response bodies, including bundle metadata. Use this when describing bundle bytes delivered to an installer.
- **Download factor:** server-to-client interface traffic, including network framing and retransmissions.
- **Total factor:** traffic in both directions, including requests and acknowledgments.

Interface totals count veth Ethernet frame bytes. Physical Ethernet preambles, frame checksums, interpacket gaps, and unrelated device traffic are excluded. Billing counters can use a different byte definition. Select a metric explicitly before applying it to a cost estimate.

## Provisional Minor-Update Factors

The two measured Bookworm update pairs give these pooled factors:

| Native Configuration | Body | Download | Total | Independent Workloads |
| --- | ---: | ---: | ---: | ---: |
| Rugix Ctrl Casync16 | 0.890 | 0.936 | 0.950 | 2 |
| RAUC 32 KiB | 1.444 | 1.544 | 1.570 | 2 |

The pooled factor is the sum of per-workload measured medians divided by the sum of modeled bytes. This weights workloads by modeled size. Major upgrades remain separate because they have different reuse and compression behavior. Five repetitions quantify variation within each image pair.

## Applying the Factors

Match each factor to the measured installer, chunking configuration, protocol, and byte metric. The Rugix Ctrl Casync16 factors describe Rugix Ctrl's implementation; the standalone Casync program needs separate transfer measurements.

The calibration covers two Bookworm minor-update pairs and one Bullseye-to-Bookworm upgrade. Its pooled factors describe the two minor updates. They have not been evaluated for Bullseye rolling updates or for quarterly and half-yearly cadences.

RAUC's transferred bytes depend on SquashFS access patterns in the running kernel. These measurements use Debian kernel 6.1.0-35-amd64.

## Data

`corrections.json` contains schema-defined per-workload factors and the pooled minor-update factors. `calculator-samples.json` and `samples.csv` retain every accepted install. `calculator-provenance.json` pins inputs and software. The model outputs are in `theory/`.
