"""Check ideal four-KiB reuse against RAUC's native provider counters."""
from __future__ import annotations

import hashlib
import re

from .common import ROOT
from .images import image_path
from .models.benchmark import Reuse, ReuseProviders

BLOCK_BYTES = 4096

def validate(plan, samples):
    """Require every RAUC sample to select the independently expected providers."""
    results = []
    candidates = {candidate.id: candidate for candidate in plan.candidates}
    for workload in plan.workloads:
        zero = bytes(BLOCK_BYTES)
        hashes = {hashlib.sha256(chunk).digest() for chunk in _chunks(image_path(workload.source.id))}
        hashes.add(hashlib.sha256(zero).digest())
        written = set()
        expected = dict(zero_chunk=0, written_prefix=0, active_slot=0, source_image=0)
        for chunk in _chunks(image_path(workload.target.id)):
            checksum = hashlib.sha256(chunk).digest()
            if chunk == zero:
                provider = "zero_chunk"
            elif checksum in written:
                provider = "written_prefix"
            elif checksum in hashes:
                provider = "active_slot"
            else:
                provider = "source_image"
            expected[provider] += 1
            written.add(checksum)
        checked = 0
        for sample in samples:
            if sample["workload"] != workload.id or candidates[sample["candidate"]].updater.tag != "Rauc":
                continue
            log = (ROOT / sample["run_directory"] / "service.log").read_text()
            fields = {key: int(float(value)) for key, value in
                      re.findall(r"access stats for (.*?): count=\d+ sum=([0-9.]+)", log)}
            mapping = {"zero_chunk": "zero chunk", "written_prefix": "target_slot_written (reusing source_image)",
                       "active_slot": "active_slot", "source_image": "source_image"}
            actual = {key: fields[value] for key, value in mapping.items()}
            if actual != expected:
                raise ValueError(f"Native reuse differs from independent expectation: {sample['run_directory']}: {actual}, expected {expected}")
            checked += 1
        chunks = sum(expected.values())
        results.append(Reuse(workload=workload.id, chunk_bytes=BLOCK_BYTES, chunks=chunks,
                             logical_missing_bytes=expected["source_image"] * BLOCK_BYTES,
                             logical_reuse_fraction=1 - expected["source_image"] / chunks,
                             providers=ReuseProviders(**expected), checked_installs=checked))
    return results

def _chunks(path):
    with path.open("rb") as image:
        while chunk := image.read(BLOCK_BYTES):
            yield chunk.ljust(BLOCK_BYTES, b"\0")
