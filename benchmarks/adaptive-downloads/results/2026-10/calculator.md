# Savings Calculator Calibration

These measurements provide provisional correction data for the existing theoretical download-size model. They do not change the calculator.

## Measured Configurations

The current calculator uses `block-based-casync-16-768` for its shared Rugix/Casync row and `block-based-fixed-4-768-32768` for its RAUC approximation. The supplemental native plan therefore measures Rugix with Casync16 and RAUC with 32 KiB XZ compression groups. Five installs at zero added RTT cover each monthly, annual, and major-upgrade pair.

| Update | Native Configuration | Model, MiB | Body Factor | Download Factor | Total Factor |
| --- | --- | ---: | ---: | ---: | ---: |
| Monthly | Rugix Casync16 | 170.14 | 0.895 | 0.942 | 0.956 |
| Monthly | RAUC 32 KiB | 180.23 | 1.453 | 1.553 | 1.579 |
| Annual | Rugix Casync16 | 221.49 | 0.887 | 0.932 | 0.945 |
| Annual | RAUC 32 KiB | 226.11 | 1.436 | 1.537 | 1.563 |
| Major | Rugix Casync16 | 369.67 | 0.883 | 0.924 | 0.939 |
| Major | RAUC 32 KiB | 356.86 | 1.385 | 1.482 | 1.507 |

Each factor divides a measured median by the original model's compressed result, including its existing 768-byte per-group allowance. Multiply that model result by the selected factor; do not add the allowance again. A factor below one means the model overestimates that byte metric.

## Keep Byte Definitions Separate

- **Body factor:** delivered HTTP response bodies, including bundle metadata. Use this when describing bundle bytes delivered to an installer.
- **Download factor:** server-to-client interface traffic, including network framing and retransmissions.
- **Total factor:** traffic in both directions, including requests and acknowledgments.

Interface totals count veth Ethernet frame bytes. Physical Ethernet preambles, frame checksums, interpacket gaps, and unrelated device traffic are excluded. Billing counters can use a different byte definition. Select a metric explicitly before applying it to a cost estimate.

## Provisional Minor-Update Factors

The two measured Bookworm update pairs give these pooled factors:

| Native Configuration | Body | Download | Total | Independent Workloads |
| --- | ---: | ---: | ---: | ---: |
| Rugix Casync16 | 0.890 | 0.936 | 0.950 | 2 |
| RAUC 32 KiB | 1.444 | 1.544 | 1.570 | 2 |

The pooled factor is the sum of per-workload measured medians divided by the sum of modeled bytes. This weights workloads by modeled size. Major upgrades remain separate because they have different reuse and compression behavior. Five repetitions quantify timing variation within a pair; they do not produce five independent workloads.

## Proposed Calculator Change

Retain the original two-year compression factors and make native correction a separate, documented layer. Match each correction to its actual tool, chunking configuration, protocol, byte metric, and measured environment.

A future implementation should split the shared Rugix/Casync label before applying a Rugix-only measurement. It should also expose or explain the selected byte definition and retain the uncorrected theoretical estimate for comparison. The provisional factors above can support a preview of this change, with the per-workload factors available in `corrections.json`.

The current calculator averages Bookworm and Bullseye results over two years and offers monthly, quarterly, half-yearly, and annual schedules. This calibration covers two Bookworm minor-update pairs and one cross-distribution upgrade. It does not validate Bullseye rolling updates or each intervening cadence. Before making a correction the default, add held-out pairs from those schedules and evaluate prediction errors.

RAUC's delivered bytes also depend on SquashFS access patterns in the running kernel. The recorded environment uses Debian kernel 6.1.0-35-amd64. A constant inferred here should be validated on another representative kernel before being described as a universal RAUC overhead factor.

## Data

`corrections.json` contains schema-defined per-workload factors and the pooled minor-update factors. `calculator-samples.json` and `samples.csv` retain every accepted install. `calculator-provenance.json` pins inputs and software. The original simulator results remain in `theory`.
