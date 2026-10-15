"""Shared paths, immutable plans and durable experiment artifacts."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
from pathlib import Path

from .models.benchmark import Plan

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache"
LOG = logging.getLogger(__name__)
BAKERY_IMAGE = "ghcr.io/rugix/rugix-bakery@sha256:7c8466d3823db8a012e20d03d523228359b1cce360ee03b3c5b9e14fbc9e11d1"
SOURCE_DATE = "2025-07-01T00:00:00Z"
SLOT_BYTES = 4 * 1024**3

def load_plan(path: Path) -> Plan:
    if not __debug__:
        raise RuntimeError("Run without Python optimization so capture validation remains enabled")
    plan = Plan.model_validate_json(path.read_text())
    if plan.schema_version != 1:
        raise ValueError("Unsupported plan schema version")
    if min(plan.repetitions, plan.rate_bits_per_second, plan.memory_mib, plan.vcpus) <= 0:
        raise ValueError("Repetitions, bandwidth and VM resources must be positive")
    if not plan.workloads or not plan.candidates or not plan.rtt_ms:
        raise ValueError("A plan requires workloads, candidates and RTTs")
    if any(rtt < 0 or rtt % 2 for rtt in plan.rtt_ms):
        raise ValueError("RTTs must be nonnegative even milliseconds")
    if len(set(plan.rtt_ms)) != len(plan.rtt_ms):
        raise ValueError("Duplicate RTT condition")
    images = {}
    for workload in plan.workloads:
        for image in (workload.source, workload.target):
            if image.id in images and images[image.id] != image:
                raise ValueError("Conflicting definitions for image " + image.id)
            images[image.id] = image
    for entries in (plan.workloads, plan.candidates, images.values()):
        identifiers = [entry.id for entry in entries]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate experiment identifier")
        if any(not re.fullmatch(r"[a-z][a-z0-9-]*", identifier) for identifier in identifiers):
            raise ValueError("Identifiers must use lowercase letters, digits and hyphens")
    for candidate in plan.candidates:
        updater = candidate.updater
        if updater.tag=="Rauc":
            if updater.version!="1.15.2":
                raise ValueError("Plan RAUC version differs from pinned runtime")
            if updater.protocol.tag=="Http2" and not updater.tls:
                raise ValueError("The pinned HTTP/2 control requires TLS")
    return plan

def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()

def fingerprint_paths(paths) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}

def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump"):
        value = value.model_dump(by_alias=True, exclude_none=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)

def read_json(path: Path):
    return json.loads(path.read_text())

def execute(command, *, cwd: Path | None = None, log: Path | None = None, **kwargs):
    LOG.info("Running %s", " ".join(map(str, command)))
    if log is None:
        return subprocess.run(command, cwd=cwd, check=True, **kwargs)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as output:
        return subprocess.run(command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT,
                              check=True, **kwargs)

def tools():
    return read_json(CACHE / "tools.json")

def bundle_key(candidate) -> str:
    updater = candidate.updater
    return ("rugix-" + updater.chunker) if updater.tag == "Rugix" else ("rauc-" + str(updater.compression_group_bytes))

def updater_path(candidate) -> str:
    if candidate.updater.tag == "Rauc":
        return tools()["runtime"] + "/bin/rauc"
    revision = candidate.updater.revision
    role = "release" if revision == "48fc40d3d903730781f3dc4bf671873d2308573a" else "pipeline"
    if revision != tools()[role + "_revision"]:
        raise ValueError("Candidate revision does not match built tools")
    return tools()[role] + "/bin/rugix-ctrl"
