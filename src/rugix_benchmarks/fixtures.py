"""Prepare blank targets and accurate native source indices before timing."""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from rugix_testkit import VMHandle

from .common import CACHE, ROOT, SLOT_BYTES, bundle_key, digest, read_json, save_json, tools
from .images import image_path
from .vm import config

ASSETS = "/run/rugix/mounts/data/bench-assets"

def prepare_disk(workload):
    path = CACHE / "disks" / (workload.id+".raw")
    source = image_path(workload.source.id)
    if path.exists():
        record = read_json(path.with_suffix(".json"))
        if record["source_sha256"] != digest(source) or record["source_bytes"] != source.stat().st_size or record["slot_bytes"] != SLOT_BYTES:
            raise ValueError("Source disk inputs changed; archive the old disk")
        return path
    if source.stat().st_size>SLOT_BYTES:
        raise ValueError("Source exceeds the four-GiB slot")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("wb") as output:
        output.truncate(9*1024**3)
    layout = "label: gpt\nunit: sectors\nstart=2048,size=8388608,type=L\nstart=8390656,size=8388608,type=L\n"
    subprocess.run(["sfdisk",str(path)],input=layout,text=True,check=True,capture_output=True)
    with source.open("rb") as original,path.open("r+b") as output:
        output.seek(1024**2)
        shutil.copyfileobj(original,output,1024**2)
    save_json(path.with_suffix(".json"),dict(source_bytes=source.stat().st_size,
              source_sha256=digest(source),slot_bytes=SLOT_BYTES))
    return path

def configure_slots(vm):
    vm.run(["systemctl","stop","rugix-ctrl-daemon.service"],check=False,hide=True)
    vm.run(["systemctl","stop","systemd-timesyncd.service"],check=False,hide=True)
    vm.upload(ROOT / "adaptive-downloads/fixtures/rugix-system.toml","/etc/rugix/system.toml")
    vm.upload(ROOT / "adaptive-downloads/fixtures/rauc-system.conf","/etc/rauc/system.conf")
    vm.run(["mount","-o","remount,rw","/run/rugix/mounts/config"],hide=True)
    vm.run(["modprobe","nbd"],hide=True)

def start_rauc(vm):
    configure_slots(vm)
    binary = tools()["runtime"]+"/bin/rauc"
    result = vm.run(["systemd-run","--unit=rauc-benchmark","--property=Type=dbus",
                    "--property=BusName=de.pengutronix.rauc",binary,"service"],
                    hide=True,check=False)
    if not result.ok:
        raise RuntimeError(vm.run(["journalctl","-u","rauc-benchmark","--no-pager"],hide=True).stdout)
    vm.run([binary,"status","mark-good"],hide=True)
    status = vm.run_json([binary,"status","--output-format=json"])
    slots = {name: value for entry in status["slots"] for name, value in entry.items()}
    if (slots["rootfs.0"]["state"] != "booted" or slots["rootfs.0"]["bootname"] != "A"
        or slots["rootfs.0"]["device"] != "/dev/vda4"
        or slots["data.0"]["state"] != "active" or slots["data.0"]["device"] != "/dev/vdb1"
        or slots["data.1"]["state"] != "inactive" or slots["data.1"]["device"] != "/dev/vdb2"):
        raise RuntimeError("Unexpected active RAUC slot configuration: " + str(status))
    return status

def prepare(plan):
    variants = {bundle_key(candidate):candidate for candidate in plan.candidates}
    chunkers = {candidate.updater.chunker for candidate in plan.candidates
                if candidate.updater.tag=="Rugix"}
    for workload in plan.workloads:
        prepare_disk(workload)
        directory = CACHE / "golden" / workload.id
        complete = directory / "fixture.json"
        if complete.exists():
            record = read_json(complete)
            if not set(variants).issubset(record["bundle_variants"]):
                raise ValueError("Prepared fixture is missing required bundle variants")
            if (record["source_sha256"] != digest(image_path(workload.source.id))
                or record["target_sha256"] != digest(image_path(workload.target.id))
                or record["native_image"]["sha256"] != read_json(CACHE / "native-image.json")["sha256"]):
                raise ValueError("Prepared fixture inputs changed; use a fresh cache")
            for role in ("release", "pipeline"):
                if record["tool_hashes"][role]["sha256"] != tools()["binaries"][role]["sha256"]:
                    raise ValueError("Prepared fixture updater changed")
            continue
        if (directory / "drive0.qcow2").exists():
            raise ValueError("Incomplete fixture exists; preserve diagnostics and use a fresh directory")
        with VMHandle.start(config(plan,workload.id,prepared=False),work_dir=directory,
                            private_key=CACHE / "keys/id_rsa",boot_timeout=180) as vm:
            configure_slots(vm)
            vm.run(["grub-editenv","/run/rugix/mounts/config/rauc.grubenv","create"],hide=True)
            vm.run(["grub-editenv","/run/rugix/mounts/config/rauc.grubenv","set",
                    "ORDER=A B","A_OK=1","A_TRY=0","B_OK=0","B_TRY=0"],hide=True)
            vm.run(["rm","-rf","/run/rugix/mounts/data/rugix/slots"],hide=True)
            binary = tools()["pipeline"]+"/bin/rugix-ctrl"
            for chunker in sorted(chunkers):
                vm.run([binary,"slots","create-index","corpus-source",chunker,"sha512-256"],
                       hide=True,timeout=600)
            status = ""
            for slot,device in (("data.0","vdb1"),("data.1","vdb2")):
                pending = "/root/rauc-corpus-data/slot."+slot+"/hash-pending"
                vm.run(["mkdir","-p",pending],hide=True)
                output = vm.run([tools()["runtime"]+"/bin/make-index","/dev/"+device,
                                 pending+"/block-hash-index"],hide=True,timeout=600).stdout
                sha,size = output.strip().split()
                vm.run(["mv",pending,pending.replace("hash-pending","hash-"+sha)],hide=True)
                status += f"[slot.{slot}]\nstatus=ok\nsha256={sha}\nsize={size}\n\n"
            initial = directory / "initial-central.raucs"
            initial.write_text(status)
            vm.upload(initial,"/root/rauc-corpus-data/central.raucs")
            for key,candidate in variants.items():
                bundle_directory = CACHE / "bundles" / workload.target.id / key
                record = read_json(bundle_directory / "bundle.json")
                vm.run(["mkdir","-p",ASSETS+"/bundles/"+key],hide=True)
                vm.upload(bundle_directory / record["filename"],ASSETS+"/bundles/"+key+"/"+record["filename"])
                vm.run(["chmod","0644",ASSETS+"/bundles/"+key+"/"+record["filename"]],hide=True)
            vm.run(["mkdir","-p",ASSETS+"/tls"],hide=True)
            for name in ("server.crt","server.key"):
                vm.upload(CACHE / "keys" / name,ASSETS+"/tls/"+name)
            vm.run(["chmod","0644",ASSETS+"/tls/server.crt"],hide=True)
            vm.run(["chmod","0600",ASSETS+"/tls/server.key"],hide=True)
            environment = vm.run(["sh","-c","uname -a; cat /etc/os-release; lsblk; findmnt; cat /proc/cmdline"],
                                 hide=True).stdout
            (directory / "environment.log").write_text(environment)
            info = vm.run_json([binary,"system","info"])
            if info["boot"]["activeGroup"]!="a":
                raise RuntimeError("Unexpected active Rugix group")
            save_json(directory / "rugix-info.json",info)
            vm.run(["sync"],hide=True)
            vm.run(["shutdown","-h","now"],check=False,hide=True)
            time.sleep(8)
        save_json(complete,dict(workload=workload.id,bundle_variants=list(variants),
                  source_sha256=digest(image_path(workload.source.id)),
                  target_sha256=digest(image_path(workload.target.id)),
                  native_image=read_json(CACHE / "native-image.json"),
                  tool_hashes=tools()["binaries"]))
