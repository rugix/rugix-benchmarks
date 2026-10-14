"""Build or import immutable Debian snapshot payloads from the original corpus."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .common import BAKERY_IMAGE, CACHE, ROOT, SOURCE_DATE, digest, execute, read_json, save_json

def prepare(plan):
    images = {image.id:image for workload in plan.workloads
              for image in (workload.source, workload.target)}
    project = CACHE / "projects/corpus"
    if not project.exists():
        shutil.copytree(ROOT / "delta-updates/rugix-project", project,
                        ignore=shutil.ignore_patterns("build", "__pycache__"))
    for image in images.values():
        destination = CACHE / "images" / image.id
        payload = destination / "root.img"
        manifest = destination / "image.json"
        if payload.exists() and manifest.exists():
            check = read_json(manifest)
            if (check["id"], check["suite"], check["snapshot"]) != (image.id, image.suite, image.snapshot):
                raise ValueError("Cached image definition changed: " + image.id)
            if digest(payload) != check["sha256"]:
                raise ValueError("Cached payload changed: " + image.id)
            continue
        layers = project / "layers"
        layers.mkdir(exist_ok=True)
        (layers / (image.id + ".toml")).write_text(f'''root = true
recipes = ["core/debian-bootstrap", "core/debian-grub-setup", "core/ssh",
           "core/set-hostname", "make-reproducible", "packages"]
[parameters."core/debian-bootstrap"]
suite = "{image.suite}"
snapshot = "{image.snapshot}"
[parameters."core/set-hostname"]
hostname = "rugix"
''')
        (project / "rugix-bakery.toml").write_text(f'''[repositories]
rugix-extra = {{ git = "https://github.com/rugix/rugix-extra.git", rev = "8dbe4f8" }}
[systems.{image.id}]
layer = "{image.id}"
architecture = "arm64"
target = "generic-grub-efi"
''')
        env = dict(os.environ, DOCKER="podman", RUGIX_DEV="true",
                   RUGIX_BAKERY_IMAGE=BAKERY_IMAGE, RUGIX_CACHE_VOLUME="rugix-benchmarks-corpus")
        execute(["./run-bakery", "bake", "image", image.id, "--release-version",
                 "20250701000000", "--source-date", SOURCE_DATE], cwd=project,
                 log=CACHE / "logs" / ("bake-" + image.id + ".log"), env=env)
        source = project / "build" / image.id / "filesystems/partition-4.img"
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, payload)
        save_json(manifest, dict(id=image.id,suite=image.suite,snapshot=image.snapshot,
                                 bytes=payload.stat().st_size,sha256=digest(payload),
                                 bakery_image=BAKERY_IMAGE,source_date=SOURCE_DATE))

def import_cache(plan, source: Path):
    """Import the pilot's unchanged corpus images with their recorded identities."""
    provenance = read_json(source / "provenance.json")
    wanted = {image.id:image for workload in plan.workloads
              for image in (workload.source,workload.target)}
    for identifier,image in wanted.items():
        record = provenance["images"][identifier]
        original = Path(record["path"])
        if original.stat().st_size!=record["bytes"] or digest(original)!=record["sha256"]:
            raise ValueError("Pilot image identity mismatch: " + identifier)
        directory = CACHE / "images" / identifier
        directory.mkdir(parents=True,exist_ok=True)
        payload = directory / "root.img"
        if not payload.exists():
            try:
                os.link(original,payload)
            except OSError:
                shutil.copyfile(original,payload)
        save_json(directory / "image.json", dict(id=identifier,suite=image.suite,
            snapshot=image.snapshot,bytes=record["bytes"],sha256=record["sha256"],
            bakery_image=BAKERY_IMAGE,source_date=SOURCE_DATE))

def image_path(identifier: str) -> Path:
    return CACHE / "images" / identifier / "root.img"
