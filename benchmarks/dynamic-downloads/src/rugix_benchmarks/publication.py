"""Render publication prose directly from complete repeated measurements."""
from __future__ import annotations

import statistics
from pathlib import Path

from .common import CACHE, ROOT, read_json


def render(plan, groups, corrections, tables, labels):
    """Keep README tables and calculator factors synchronized."""
    monthly = lambda candidate, rtt: groups["monthly", candidate, rtt]
    median = lambda candidate, rtt, field: statistics.median(row[field] for row in monthly(candidate, rtt))
    speedups40 = [statistics.median(_paired(groups, workload.id, 40, "rugix-release", "rugix-pipeline"))
                  for workload in plan.workloads]
    rauc_speedups40 = [statistics.median(_paired(groups, workload.id, 40, "rauc-http", "rugix-pipeline"))
                       for workload in plan.workloads]
    monthly_total = statistics.median(row["download_bytes"] + row["upload_bytes"] for row in monthly("rugix-pipeline", 10))
    monthly_rauc_total = statistics.median(row["download_bytes"] + row["upload_bytes"] for row in monthly("rauc-http", 10))
    correction = {(row["candidate"], row["workload"]): row for row in corrections}
    rugix = correction["rugix-pipeline-casync16", "minor-pooled"]
    rauc = correction["rauc-http-32k", "minor-pooled"]
    pipeline = correction["rugix-pipeline", "monthly"]
    rauc64 = correction["rauc-http", "monthly"]
    major_rauc = groups["major", "rauc-http", 10]
    major_rauc_body = statistics.median(row["body_bytes"] for row in major_rauc)
    major_rauc_bundle = statistics.median(row["bundle_bytes"] for row in major_rauc)
    target_id = next(workload.target.id for workload in plan.workloads if workload.id == "monthly")
    baseline = read_json(CACHE / "theory" / target_id / "base.json")["compressed"]
    calibration_table = ["| Update | Native Configuration | Model, MiB | Body Factor | Download Factor | Total Factor |",
                         "| --- | --- | ---: | ---: | ---: | ---: |"]
    for row in corrections:
        if row["candidate"] in ("rugix-pipeline-casync16", "rauc-http-32k") and row["workload"] != "minor-pooled":
            calibration_table.append(f"| {row['workload'].title()} | {labels[row['candidate']]} | {row['model_bytes'] / 1024**2:.2f} | {row['body_factor']:.3f} | {row['download_factor']:.3f} | {row['total_factor']:.3f} |")
    context = dict(
        tables="\n".join(tables).replace("## ", "### "),
        calibration_table="\n".join(calibration_table),
        monthly_new40=median("rugix-pipeline", 40, "seconds"),
        monthly_new40_min=min(row["seconds"] for row in monthly("rugix-pipeline", 40)),
        monthly_new40_max=max(row["seconds"] for row in monthly("rugix-pipeline", 40)),
        monthly_old40=median("rugix-release", 40, "seconds"),
        monthly_rauc40=median("rauc-http", 40, "seconds"),
        speedup40_low=min(speedups40), speedup40_high=max(speedups40),
        rauc_speedup40_low=min(rauc_speedups40), rauc_speedup40_high=max(rauc_speedups40),
        monthly_traffic_reduction_pct=100 * (1 - monthly_total / monthly_rauc_total),
        monthly_old_connections=median("rugix-release", 10, "connections"),
        monthly_new_connections=median("rugix-pipeline", 10, "connections"),
        monthly_body_mib=median("rugix-pipeline", 10, "body_bytes") / 1024**2,
        monthly_total_mib=monthly_total / 1024**2,
        monthly_rauc_body_mib=median("rauc-http", 10, "body_bytes") / 1024**2,
        monthly_rauc_total_mib=monthly_rauc_total / 1024**2,
        rugix_bundle_mib=median("rugix-pipeline", 10, "bundle_bytes") / 1024**2,
        rauc_bundle_mib=median("rauc-http", 10, "bundle_bytes") / 1024**2,
        major_rauc_body_mib=major_rauc_body / 1024**2,
        major_rauc_bundle_ratio=major_rauc_body / major_rauc_bundle,
        baseline_mib=baseline / 1024**2,
        monthly_body_factor=pipeline["body_factor"], monthly_total_factor=pipeline["total_factor"],
        monthly_rauc_body_factor=rauc64["body_factor"], monthly_rauc_total_factor=rauc64["total_factor"],
        rugix_pooled_body=rugix["body_factor"], rugix_pooled_download=rugix["download_factor"], rugix_pooled_total=rugix["total_factor"],
        rauc_pooled_body=rauc["body_factor"], rauc_pooled_download=rauc["download_factor"], rauc_pooled_total=rauc["total_factor"],
    )
    templates = Path(__file__).with_name("templates")
    for name, destination in (
        ("readme.md", ROOT / "README.md"),
        ("calculator.md", ROOT / "results/2026-10/calculator.md"),
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((templates / name).read_text().format_map(context))
    return context


def _paired(groups, workload, rtt, numerator, denominator):
    first = {row["repetition"]: row["seconds"] for row in groups[workload, numerator, rtt]}
    second = {row["repetition"]: row["seconds"] for row in groups[workload, denominator, rtt]}
    return [first[repetition] / second[repetition] for repetition in first]
