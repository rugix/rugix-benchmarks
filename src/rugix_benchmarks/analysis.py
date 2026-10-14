"""Validate complete campaigns and export repeated measurements for publication."""
from __future__ import annotations

import csv
import shutil
import statistics
from collections import defaultdict
from pathlib import Path

from matplotlib import pyplot as plt

from .common import CACHE, ROOT, bundle_key, digest, load_plan, read_json, save_json
from .models.benchmark import Correction, Sample
from .reuse import validate as validate_reuse
from .publication import render as render_publication

plt.switch_backend("Agg")

MIB = 1024**2
LABELS = {
    "rugix-release": "Rugix v1.3.0",
    "rugix-pipeline": "Rugix pipeline PR",
    "rauc-http": "RAUC HTTP/1.1",
    "rauc-tls-h1": "RAUC TLS HTTP/1.1",
    "rauc-tls-h2": "RAUC TLS HTTP/2",
    "rugix-pipeline-casync16": "Rugix Casync16",
    "rauc-http-32k": "RAUC 32 KiB",
}

def report(paper: Path, calibration: Path):
    """Require every planned sample before generating publication artifacts."""
    paper_plan, paper_samples = _load_complete(paper)
    calibration_plan, calibration_samples = _load_complete(calibration)
    output = ROOT / "results/2026-10"
    output.mkdir(parents=True, exist_ok=True)
    for name, directory in (("paper", paper), ("calculator", calibration)):
        for filename in ("plan.json", "samples.json", "provenance.json"):
            shutil.copyfile(directory / filename, output / (name + "-" + filename))
    samples = paper_samples + calibration_samples
    with (output / "samples.csv").open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(samples[0]))
        writer.writeheader()
        writer.writerows(samples)
    groups = _groups(paper_samples)
    tables = []
    for workload in paper_plan.workloads:
        tables += ["## " + workload.id.title() + " Update", "",
                   "| Installer | 0 ms, s | 10 ms, s | 40 ms, s |",
                   "| --- | ---: | ---: | ---: |"]
        for candidate in paper_plan.candidates:
            values = [_time_cell(groups[workload.id, candidate.id, rtt]) for rtt in paper_plan.rtt_ms]
            tables.append("| " + LABELS[candidate.id] + " | " + " | ".join(values) + " |")
        tables += ["", "Times are medians with the interquartile range in brackets, from five installs per cell.", ""]
    tables += ["## Download Size and Traffic", "",
               "The table uses 10 ms RTT and five repetitions. Body bytes count delivered HTTP response bodies. Link traffic includes both directions, including headers, acknowledgments and retransmissions.", "",
               "| Update | Installer | Body, MiB | Link Download, MiB | Link Total, MiB | Requests | Connections |",
               "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for workload in paper_plan.workloads:
        for candidate in paper_plan.candidates:
            rows = groups[workload.id, candidate.id, 10]
            values = [_median(rows, field) / MIB for field in ("body_bytes", "download_bytes")]
            total = statistics.median(row["download_bytes"] + row["upload_bytes"] for row in rows) / MIB
            tables.append(f"| {workload.id.title()} | {LABELS[candidate.id]} | {values[0]:.2f} | {values[1]:.2f} | {total:.2f} | {_median(rows, 'requests'):.0f} | {_median(rows, 'connections'):.0f} |")
    tables += ["", "## Pipeline Speedup", "",
               "Each ratio pairs a release and pipeline install from the same repetition, workload and RTT.", "",
               "| Update | RTT | Median Speedup | Paired Range |",
               "| --- | ---: | ---: | ---: |"]
    for workload in paper_plan.workloads:
        for rtt in paper_plan.rtt_ms:
            old = {row["repetition"]: row["seconds"] for row in groups[workload.id, "rugix-release", rtt]}
            new = {row["repetition"]: row["seconds"] for row in groups[workload.id, "rugix-pipeline", rtt]}
            ratios = [old[rep] / new[rep] for rep in old]
            tables.append(f"| {workload.id.title()} | {rtt} ms | {statistics.median(ratios):.2f}× | {min(ratios):.2f}–{max(ratios):.2f}× |")
    tables += ["", "## Theory and Measured Overhead", "",
               "The original model includes 768 bytes per downloaded compression group. Its compressed result is compared directly with native delivered bytes and complete link traffic.", "",
               "| Update | Installer | Model, MiB | Body / Model | Download / Model | Total / Model |",
               "| --- | --- | ---: | ---: | ---: | ---: |"]
    corrections = []
    for plan, rows, rtt in ((paper_plan, paper_samples, 10), (calibration_plan, calibration_samples, 0)):
        grouped = _groups(rows)
        for workload in plan.workloads:
            for candidate in plan.candidates:
                group = grouped[workload.id, candidate.id, rtt]
                model = read_json(CACHE / "theory" / workload.id / (bundle_key(candidate) + ".json"))["compressed"]
                correction = Correction(candidate=candidate.id, workload=workload.id, model_bytes=model,
                    body_factor=_median(group, "body_bytes") / model,
                    download_factor=_median(group, "download_bytes") / model,
                    total_factor=statistics.median(row["download_bytes"] + row["upload_bytes"] for row in group) / model,
                    independent_workloads=1)
                corrections.append(correction.model_dump(by_alias=True))
                tables.append(f"| {workload.id.title()} | {LABELS[candidate.id]} | {model / MIB:.2f} | {correction.body_factor:.3f} | {correction.download_factor:.3f} | {correction.total_factor:.3f} |")
                target = output / "theory" / workload.id / (bundle_key(candidate) + ".json")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(CACHE / "theory" / workload.id / (bundle_key(candidate) + ".json"), target)
    for candidate in calibration_plan.candidates:
        minor = [row for row in corrections if row["candidate"] == candidate.id and row["workload"] in ("monthly", "annual")]
        total_model = sum(row["model_bytes"] for row in minor)
        pooled = dict(candidate=candidate.id, workload="minor-pooled", model_bytes=total_model,
                      independent_workloads=len(minor))
        for field in ("body_factor", "download_factor", "total_factor"):
            pooled[field] = sum(row[field] * row["model_bytes"] for row in minor) / total_model
        corrections.append(Correction.model_validate(pooled).model_dump(by_alias=True))
    combined = paper_plan.model_copy(update={"candidates": paper_plan.candidates + calibration_plan.candidates})
    reuse = validate_reuse(combined, samples)
    save_json(output / "reuse.json", [item.model_dump(by_alias=True) for item in reuse])
    tables += ["", "## RAUC Block Reuse", "",
               "Independent 4 KiB matching must agree with every native RAUC install, including zero blocks and reuse from the already written target prefix.", "",
               "| Update | Logical Reuse | Missing Raw Data, MiB | Checked Installs |",
               "| --- | ---: | ---: | ---: |"]
    for item in reuse:
        tables.append(f"| {item.workload.title()} | {item.logical_reuse_fraction:.1%} | {item.logical_missing_bytes / MIB:.2f} | {item.checked_installs} |")
    save_json(output / "corrections.json", corrections)
    (output / "tables.md").write_text("\n".join(tables) + "\n")
    summary = [
        dict(workload=workload, candidate=candidate, rtt_ms=rtt, repetitions=len(rows),
             seconds_median=_median(rows, "seconds"),
             seconds_q1=_quartiles(rows)[0], seconds_q3=_quartiles(rows)[1],
             seconds_minimum=min(row["seconds"] for row in rows),
             seconds_maximum=max(row["seconds"] for row in rows))
        for (workload, candidate, rtt), rows in groups.items()
    ]
    save_json(output / "summary.json", summary)
    article_groups = []
    for item in summary:
        rows = groups[item["workload"], item["candidate"], item["rtt_ms"]]
        article_groups.append(dict(item,
            seconds_samples=[row["seconds"] for row in sorted(rows, key=lambda row: row["repetition"])],
            body_bytes_median=_median(rows, "body_bytes"),
            download_bytes_median=_median(rows, "download_bytes"),
            total_bytes_median=statistics.median(row["download_bytes"] + row["upload_bytes"] for row in rows)))
    save_json(output / "article-data.json", dict(
        plan_sha256=digest(paper / "plan.json"), groups=article_groups))
    for target_id in {workload.target.id for workload in paper_plan.workloads}:
        target = output / "theory" / target_id / "base.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CACHE / "theory" / target_id / "base.json", target)
    _plots(paper_plan, groups, output)
    _traffic_plot(paper_plan, groups, output)
    render_publication(paper_plan, groups, corrections, tables, LABELS)
    print(f"Validated {len(paper_samples)} main and {len(calibration_samples)} calibration installs. Results: {output}")

def _load_complete(directory):
    plan = load_plan(directory / "plan.json")
    plan_hash = digest(directory / "plan.json")
    rows = [Sample.model_validate(row).model_dump(by_alias=True) for row in read_json(directory / "samples.json")]
    expected = {(workload.id, candidate.id, rtt, repetition) for workload in plan.workloads
                for candidate in plan.candidates for rtt in plan.rtt_ms for repetition in range(plan.repetitions)}
    observed = {(row["workload"], row["candidate"], row["rtt_ms"], row["repetition"]) for row in rows}
    if observed != expected or len(rows) != len(expected):
        raise ValueError(f"Incomplete or duplicate campaign: {directory}")
    provenance = read_json(directory / "provenance.json")
    candidates = {candidate.id: candidate for candidate in plan.candidates}
    model_paths = {CACHE / "theory" / workload.id / (bundle_key(candidate) + ".json")
                   for workload in plan.workloads for candidate in plan.candidates}
    model_paths |= {CACHE / "theory" / workload.target.id / "base.json" for workload in plan.workloads}
    for path in model_paths:
        if provenance["files"].get(str(path.relative_to(ROOT))) != digest(path):
            raise ValueError("Theoretical model differs from campaign provenance: " + str(path))
    for row in rows:
        if row["plan_sha256"] != plan_hash or row["seconds"] <= 0:
            raise ValueError("Incompatible or invalid sample")
        workload = next(item for item in plan.workloads if item.id == row["workload"])
        bundle = provenance["bundles"][workload.target.id + "/" + bundle_key(candidates[row["candidate"]])]
        if (row["payload_sha256"] != bundle["payload"]["sha256"]
            or row["source_sha256"] != provenance["fixtures"][workload.id]["source_sha256"]
            or row["bundle_sha256"] != bundle["sha256"]):
            raise ValueError("Sample input or reconstructed payload differs")
        durable = ROOT / row["run_directory"] / "result.json"
        if read_json(durable) != row:
            raise ValueError("Sample differs from its durable evidence")
    return plan, rows

def _groups(samples):
    groups = defaultdict(list)
    for row in samples:
        groups[row["workload"], row["candidate"], row["rtt_ms"]].append(row)
    return groups

def _median(rows, field):
    return statistics.median(row[field] for row in rows)

def _quartiles(rows):
    values = statistics.quantiles([row["seconds"] for row in rows], n=4, method="inclusive")
    return values[0], values[2]

def _time_cell(rows):
    q1, q3 = _quartiles(rows)
    return f"{_median(rows, 'seconds'):.1f} [{q1:.1f}, {q3:.1f}]"

def _plots(plan, groups, output):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"})
    figure, axes = plt.subplots(1, len(plan.workloads), figsize=(12, 4.3), sharey=True)
    colors = ["#667085", "#2463eb", "#d97706", "#b45309", "#7c3aed"]
    for axis, workload in zip(axes, plan.workloads):
        for candidate, color in zip(plan.candidates, colors):
            medians = [_median(groups[workload.id, candidate.id, rtt], "seconds") for rtt in plan.rtt_ms]
            quartiles = [_quartiles(groups[workload.id, candidate.id, rtt]) for rtt in plan.rtt_ms]
            axis.errorbar(plan.rtt_ms, medians, yerr=[
                [median - q[0] for median, q in zip(medians, quartiles)],
                [q[1] - median for median, q in zip(medians, quartiles)]],
                color=color, marker="o", capsize=3, label=LABELS[candidate.id])
            for rtt in plan.rtt_ms:
                axis.scatter([rtt] * len(groups[workload.id, candidate.id, rtt]),
                             [row["seconds"] for row in groups[workload.id, candidate.id, rtt]],
                             color=color, s=9, alpha=.35)
        axis.set_title(workload.id.title() + " Update")
        axis.set_xlabel("Added round-trip latency (ms)")
        axis.set_xticks(plan.rtt_ms)
        axis.grid(axis="y", alpha=.2)
    axes[0].set_ylabel("Verified installation time (s)")
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    figure.tight_layout(rect=(0, .14, 1, 1))
    for suffix in ("svg", "pdf", "png"):
        figure.savefig(output / ("installation-time." + suffix), dpi=200)
    plt.close(figure)

def _traffic_plot(plan, groups, output):
    figure, axes = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True)
    positions = list(range(len(plan.workloads)))
    candidates = ("rugix-release", "rugix-pipeline", "rauc-http")
    colors = ("#667085", "#2463eb", "#d97706")
    for index, (candidate, color) in enumerate(zip(candidates, colors)):
        x = [position + (index - 1) * .23 for position in positions]
        rows = [groups[workload.id, candidate, 10] for workload in plan.workloads]
        axes[0].bar(x, [_median(group, "body_bytes") / MIB for group in rows],
                    width=.20, color=color, label=LABELS[candidate])
        axes[1].bar(x, [statistics.median(row["download_bytes"] + row["upload_bytes"] for row in group) / MIB for group in rows],
                    width=.20, color=color)
    for position, workload in zip(positions, plan.workloads):
        baseline = read_json(CACHE / "theory" / workload.target.id / "base.json")["compressed"] / MIB
        axes[0].plot([position - .37, position + .37], [baseline, baseline],
                     color="#111827", linestyle="--", linewidth=1.2,
                     label="Whole-image XZ size" if position == 0 else None)
    axes[0].set_ylabel("Delivered HTTP bodies (MiB)")
    axes[1].set_ylabel("Bidirectional interface traffic (MiB)")
    axes[1].set_xticks(positions, [workload.id.title() for workload in plan.workloads])
    axes[0].legend(loc="upper left", ncol=2, frameon=False)
    for axis in axes:
        axis.grid(axis="y", alpha=.2)
        axis.set_axisbelow(True)
    figure.suptitle("Native traffic at 10 ms RTT, median of five installs")
    figure.tight_layout()
    for suffix in ("svg", "pdf", "png"):
        figure.savefig(output / ("download-size." + suffix), dpi=200)
    plt.close(figure)
