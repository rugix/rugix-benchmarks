"""Pin both native Rugix builds and archive their guest runtime dependencies."""
from __future__ import annotations

import json
import subprocess
import tarfile
from pathlib import Path

from .common import CACHE, ROOT, digest, read_json, save_json

RELEASE = "48fc40d3d903730781f3dc4bf671873d2308573a"
PIPELINE = "b82749ff34ee8668fb3e53322af039a083e8bf69"

def prepare():
    output = CACHE / "tools-build.json"
    prior = read_json(CACHE / "tools.json") if (CACHE / "tools.json").exists() else {}
    CACHE.mkdir(parents=True, exist_ok=True)
    result = subprocess.check_output(["nix", "build", "--no-link", "--json",
        "path:" + str(ROOT / "nix") + "#rugix-release",
        "path:" + str(ROOT / "nix") + "#rugix-pipeline",
        "path:" + str(ROOT / "nix") + "#runtime"], text=True)
    output.write_text(result)
    results = json.loads(output.read_text())
    paths = {}
    for result in results:
        path = result["outputs"]["out"]
        name = Path(path).name
        if name.endswith("-v1.3.0"):
            paths["release"] = path
        elif name.endswith("-b82749f"):
            paths["pipeline"] = path
        elif name.endswith("-rugix-benchmark-runtime"):
            paths["runtime"] = path
    assert set(paths) == {"release", "pipeline", "runtime"}, paths
    paths.update(release_revision=RELEASE, pipeline_revision=PIPELINE)
    paths["binaries"] = {}
    for role in ("release", "pipeline"):
        binary = Path(paths[role]) / "bin/rugix-ctrl"
        paths["binaries"][role] = dict(sha256=digest(binary),
            version=subprocess.check_output([str(binary), "--version"], text=True).strip())
    for name,flags in (("rauc",["--version"]),("nginx",["-v"]),("iperf3",["--version"]),("tcpdump",["--version"]),("ethtool",["--version"])):
        binary = Path(paths["runtime"]) / "bin" / name
        paths["binaries"][name] = dict(sha256=digest(binary),version=subprocess.check_output([str(binary),*flags],stderr=subprocess.STDOUT,text=True).strip())
    link_dir = CACHE / "bin"
    link_dir.mkdir(exist_ok=True)
    link = link_dir / "rugix-bundler"
    if link.is_symlink():
        link.unlink()
    link.symlink_to(Path(paths["pipeline"]) / "bin/rugix-bundler")
    roots = [paths["runtime"], paths["release"], paths["pipeline"]]
    closure = sorted(set(subprocess.check_output(["nix", "path-info", "-r", *roots],
                                                  text=True).splitlines()))
    archive = CACHE / "runtime.tar.gz"
    if not archive.exists() or prior.get("guest_closure") != closure:
        with tarfile.open(archive, "w:gz") as output_tar:
            for path in closure:
                output_tar.add(path, arcname=path.lstrip("/"))
    paths["runtime_archive_sha256"] = digest(archive)
    paths["guest_closure"] = closure
    save_json(CACHE / "tools.json", paths)
    return paths
