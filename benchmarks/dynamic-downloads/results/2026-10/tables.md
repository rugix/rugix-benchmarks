## Monthly Update

| Installer | 0 ms, s | 10 ms, s | 40 ms, s |
| --- | ---: | ---: | ---: |
| Rugix Ctrl 1.3.0 | 16.4 [15.8, 17.9] | 134.8 [131.3, 135.1] | 457.6 [457.4, 458.0] |
| Rugix Ctrl concurrent fetcher | 18.8 [16.4, 21.5] | 18.8 [17.3, 23.5] | 31.0 [27.2, 40.5] |
| RAUC HTTP/1.1 | 24.9 [23.7, 26.0] | 134.6 [132.6, 138.2] | 440.5 [440.0, 441.0] |
| RAUC TLS HTTP/1.1 | 28.2 [27.8, 29.5] | 138.9 [133.4, 142.9] | 444.5 [441.6, 448.0] |
| RAUC TLS HTTP/2 | 24.9 [24.7, 26.3] | 138.8 [136.4, 140.9] | 441.8 [436.9, 442.7] |

Columns show added round-trip time in milliseconds. Installation times are seconds, shown as median [first quartile, third quartile] from five installs.

## Annual Update

| Installer | 0 ms, s | 10 ms, s | 40 ms, s |
| --- | ---: | ---: | ---: |
| Rugix Ctrl 1.3.0 | 18.3 [18.2, 18.5] | 160.9 [160.9, 166.1] | 566.2 [565.7, 567.5] |
| Rugix Ctrl concurrent fetcher | 19.3 [18.1, 19.9] | 18.6 [17.5, 19.2] | 24.2 [23.8, 25.2] |
| RAUC HTTP/1.1 | 31.0 [30.2, 32.5] | 175.4 [167.7, 177.9] | 570.0 [569.9, 573.0] |
| RAUC TLS HTTP/1.1 | 31.3 [29.9, 33.5] | 179.4 [175.4, 179.9] | 575.9 [573.0, 590.1] |
| RAUC TLS HTTP/2 | 29.6 [28.7, 32.2] | 176.1 [175.8, 182.2] | 574.1 [572.5, 576.1] |

Columns show added round-trip time in milliseconds. Installation times are seconds, shown as median [first quartile, third quartile] from five installs.

## Major Update

| Installer | 0 ms, s | 10 ms, s | 40 ms, s |
| --- | ---: | ---: | ---: |
| Rugix Ctrl 1.3.0 | 23.2 [22.4, 24.5] | 219.3 [219.2, 219.7] | 805.9 [805.6, 806.0] |
| Rugix Ctrl concurrent fetcher | 23.2 [22.1, 24.5] | 23.0 [22.1, 23.0] | 26.4 [26.2, 26.4] |
| RAUC HTTP/1.1 | 36.0 [33.1, 52.7] | 246.0 [242.0, 248.9] | 821.1 [821.0, 822.7] |
| RAUC TLS HTTP/1.1 | 36.0 [35.8, 37.7] | 246.6 [246.4, 251.5] | 821.8 [819.9, 822.5] |
| RAUC TLS HTTP/2 | 37.1 [34.9, 38.6] | 249.6 [244.6, 252.1] | 821.3 [818.0, 822.1] |

Columns show added round-trip time in milliseconds. Installation times are seconds, shown as median [first quartile, third quartile] from five installs.

## Download Size and Traffic

Values are medians of five installs at 10 ms added RTT. Body counts delivered HTTP response-body bytes; Link Download counts server-to-client interface bytes; Link Total includes interface traffic in both directions.

| Update | Installer | Body, MiB | Link Download, MiB | Link Total, MiB | Requests | Connections |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Monthly | Rugix Ctrl 1.3.0 | 180.66 | 190.36 | 197.09 | 2750 | 2750 |
| Monthly | Rugix Ctrl concurrent fetcher | 165.69 | 173.65 | 175.91 | 931 | 4 |
| Monthly | RAUC HTTP/1.1 | 229.97 | 243.78 | 246.12 | 9932 | 16 |
| Monthly | RAUC TLS HTTP/1.1 | 229.97 | 244.81 | 247.40 | 9932 | 15 |
| Monthly | RAUC TLS HTTP/2 | 229.97 | 244.19 | 247.32 | 9932 | 1 |
| Annual | Rugix Ctrl 1.3.0 | 224.50 | 236.55 | 244.96 | 3429 | 3429 |
| Annual | Rugix Ctrl concurrent fetcher | 209.08 | 219.07 | 222.28 | 963 | 4 |
| Annual | RAUC HTTP/1.1 | 285.36 | 302.69 | 305.70 | 12933 | 16 |
| Annual | RAUC TLS HTTP/1.1 | 285.36 | 303.93 | 307.27 | 12933 | 15 |
| Annual | RAUC TLS HTTP/2 | 285.36 | 303.11 | 307.17 | 12933 | 1 |
| Major | Rugix Ctrl 1.3.0 | 314.67 | 331.59 | 343.49 | 4832 | 4832 |
| Major | Rugix Ctrl concurrent fetcher | 311.34 | 325.88 | 331.13 | 479 | 4 |
| Major | RAUC HTTP/1.1 | 414.72 | 439.89 | 444.20 | 18723 | 16 |
| Major | RAUC TLS HTTP/1.1 | 414.72 | 441.65 | 446.43 | 18723 | 16 |
| Major | RAUC TLS HTTP/2 | 414.72 | 440.49 | 446.33 | 18723 | 1 |

## Rugix Ctrl Speedup

Each speedup is the Rugix Ctrl 1.3.0 time divided by the concurrent fetcher time for the same repetition, workload, and added RTT. The table gives the median and full range of five paired ratios.

| Update | RTT | Median Speedup | Paired Range |
| --- | ---: | ---: | ---: |
| Monthly | 0 ms | 0.97× | 0.74–1.26× |
| Monthly | 10 ms | 7.82× | 4.92–8.95× |
| Monthly | 40 ms | 14.75× | 7.09–18.95× |
| Annual | 0 ms | 1.01× | 0.87–1.15× |
| Annual | 10 ms | 8.66× | 6.05–9.71× |
| Annual | 40 ms | 23.50× | 20.00–25.19× |
| Major | 0 ms | 1.00× | 0.57–1.16× |
| Major | 10 ms | 9.67× | 9.20–10.05× |
| Major | 40 ms | 30.58× | 26.19–35.21× |

## Theory and Measured Overhead

The model estimates compressed data and index bytes plus 768 bytes per downloaded compression group. Each factor is measured bytes divided by modeled bytes: values above one indicate an underestimate. Main configurations use five installs at 10 ms added RTT; Casync16 and RAUC 32 KiB use five installs at zero added RTT.

| Update | Installer | Model, MiB | Body / Model | Download / Model | Total / Model |
| --- | --- | ---: | ---: | ---: | ---: |
| Monthly | Rugix Ctrl 1.3.0 | 171.09 | 1.056 | 1.113 | 1.152 |
| Monthly | Rugix Ctrl concurrent fetcher | 171.09 | 0.968 | 1.015 | 1.028 |
| Monthly | RAUC HTTP/1.1 | 179.27 | 1.283 | 1.360 | 1.373 |
| Monthly | RAUC TLS HTTP/1.1 | 179.27 | 1.283 | 1.366 | 1.380 |
| Monthly | RAUC TLS HTTP/2 | 179.27 | 1.283 | 1.362 | 1.380 |
| Annual | Rugix Ctrl 1.3.0 | 216.49 | 1.037 | 1.093 | 1.131 |
| Annual | Rugix Ctrl concurrent fetcher | 216.49 | 0.966 | 1.012 | 1.027 |
| Annual | RAUC HTTP/1.1 | 222.46 | 1.283 | 1.361 | 1.374 |
| Annual | RAUC TLS HTTP/1.1 | 222.46 | 1.283 | 1.366 | 1.381 |
| Annual | RAUC TLS HTTP/2 | 222.46 | 1.283 | 1.363 | 1.381 |
| Major | Rugix Ctrl 1.3.0 | 322.76 | 0.975 | 1.027 | 1.064 |
| Major | Rugix Ctrl concurrent fetcher | 322.76 | 0.965 | 1.010 | 1.026 |
| Major | RAUC HTTP/1.1 | 335.64 | 1.236 | 1.311 | 1.323 |
| Major | RAUC TLS HTTP/1.1 | 335.64 | 1.236 | 1.316 | 1.330 |
| Major | RAUC TLS HTTP/2 | 335.64 | 1.236 | 1.312 | 1.330 |
| Monthly | Rugix Ctrl Casync16 | 170.14 | 0.895 | 0.942 | 0.956 |
| Monthly | RAUC 32 KiB | 180.23 | 1.453 | 1.553 | 1.579 |
| Annual | Rugix Ctrl Casync16 | 221.49 | 0.887 | 0.932 | 0.945 |
| Annual | RAUC 32 KiB | 226.11 | 1.436 | 1.537 | 1.563 |
| Major | Rugix Ctrl Casync16 | 369.67 | 0.883 | 0.924 | 0.939 |
| Major | RAUC 32 KiB | 356.86 | 1.385 | 1.482 | 1.507 |

## RAUC Block Reuse

Logical Reuse is the fraction of target 4 KiB blocks supplied by source blocks, zero data, or data already written to the target. Missing Raw Data counts the remaining blocks before compression. For every checked install, RAUC reuse counters matched an independent block comparison.

| Update | Logical Reuse | Missing Raw Data, MiB | Checked Installs |
| --- | ---: | ---: | ---: |
| Monthly | 71.7% | 399.73 | 50 |
| Annual | 58.4% | 587.56 | 50 |
| Major | 27.9% | 1017.69 | 50 |
