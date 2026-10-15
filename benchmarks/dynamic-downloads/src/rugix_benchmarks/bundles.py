"""Package identical corpus payloads and compute the original byte estimates."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .common import CACHE, bundle_key, digest, execute, read_json, save_json, tools
from .images import image_path

def prepare(plan):
    targets = {workload.target.id for workload in plan.workloads}
    unique = {bundle_key(candidate):candidate for candidate in plan.candidates}
    for target in targets:
        for key,candidate in unique.items():
            directory = CACHE / "bundles" / target / key
            manifest = directory / "bundle.json"
            if manifest.exists():
                record = read_json(manifest)
                if digest(directory / record["filename"])!=record["sha256"]:
                    raise ValueError("Cached bundle changed: " + key)
                continue
            payloads = directory / "payloads"
            payloads.mkdir(parents=True,exist_ok=True)
            payload = payloads / "root.img"
            shutil.copyfile(image_path(target),payload)
            original_size = payload.stat().st_size
            with payload.open("ab") as output:
                output.write(bytes((-original_size)%4096))
            identity = dict(bytes=payload.stat().st_size,sha256=digest(payload))
            updater = candidate.updater
            bundler = str(Path(tools()["pipeline"]) / "bin/rugix-bundler")
            if updater.tag=="Rugix":
                filename = "system.rugixb"
                (directory / "rugix-bundle.toml").write_text(f'''update-type = "incremental"
[[payloads]]
filename = "root.img"
[payloads.delivery]
type = "slot"
slot = "corpus-target"
[payloads.block-encoding]
chunker = "{updater.chunker}"
deduplicate = true
[payloads.block-encoding.compression]
type = "xz"
''')
                execute([bundler,"bundle",str(directory),str(directory / filename)],
                        log=CACHE / "logs" / f"bundle-{target}-{key}.log")
                trusted_hash = subprocess.check_output([bundler,"hash",str(directory / filename)],
                                                        text=True).strip()
            else:
                filename = "system.raucb"
                trusted_hash = None
                (payloads / "manifest.raucm").write_text('''[update]
compatible=rugix-benchmarks
version=1
[bundle]
format=verity
[image.data]
filename=root.img
adaptive=block-hash-index
''')
                keys = CACHE / "keys"
                execute([tools()["runtime"]+"/bin/rauc","bundle",
                    "--cert="+str(keys / "signer.crt"),"--key="+str(keys / "signer.key"),
                    "--mksquashfs-args=-comp xz -b "+str(updater.compression_group_bytes)+" -processors 4",
                    str(payloads),str(directory / filename)],
                    log=CACHE / "logs" / f"bundle-{target}-{key}.log")
            save_json(manifest,dict(filename=filename,bytes=(directory / filename).stat().st_size,
                sha256=digest(directory / filename),payload=identity,trusted_hash=trusted_hash))
            payload.unlink()

def simulate(plan):
    bundler = str(Path(tools()["pipeline"]) / "bin/rugix-bundler")
    strategies = {}
    for candidate in plan.candidates:
        updater = candidate.updater
        key = bundle_key(candidate)
        strategies[key] = dict(chunker=updater.chunker if updater.tag=="Rugix" else "fixed-4",
                               group_size=None if updater.tag=="Rugix" else updater.compression_group_bytes)
    for workload in plan.workloads:
        for key,strategy in strategies.items():
            path = CACHE / "theory" / workload.id / (key+".json")
            if path.exists():
                continue
            command = [bundler,"simulator","block-based","simulate","--chunker",strategy["chunker"],
                       "--group-overhead","768"]
            if strategy["group_size"]:
                command += ["--group-size",str(strategy["group_size"])]
            command += [str(image_path(workload.source.id)),str(image_path(workload.target.id))]
            result = subprocess.check_output(command)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(result)
        baseline = CACHE / "theory" / workload.target.id / "base.json"
        if not baseline.exists():
            payload = image_path(workload.target.id)
            compressed = subprocess.check_output(["xz","-c","-6",str(payload)])
            save_json(baseline,dict(uncompressed=payload.stat().st_size,compressed=len(compressed)))
