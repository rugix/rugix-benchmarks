"""Boot immutable Bakery images and disposable native benchmark fixtures."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from rugix_testkit import Drive, Pflash, VMConfig

from .common import BAKERY_IMAGE, CACHE, ROOT, SOURCE_DATE, digest, execute, fingerprint_paths, read_json, save_json, tools

def build_native_image():
    image = CACHE / "projects/native/build/benchmark-amd64/system.img"
    project = CACHE / "projects/native"
    template = ROOT / "adaptive-downloads/bakery"
    inputs = dict(bakery_image=BAKERY_IMAGE, source_date=SOURCE_DATE,
                  recipes=fingerprint_paths(path for path in template.rglob("*") if path.is_file()),
                  runtime_archive_sha256=tools()["runtime_archive_sha256"],
                  ssh_key_sha256=digest(CACHE / "keys/id_rsa.pub"),
                  signing_ca_sha256=digest(CACHE / "keys/ca.crt"))
    manifest = CACHE / "native-image.json"
    if image.exists():
        record = read_json(manifest)
        if record.get("inputs") != inputs:
            raise ValueError("Native image inputs changed; archive the old image and rebuild")
        if digest(image) != record["sha256"]:
            raise ValueError("Native image differs from its manifest")
        return image
    if (project / "recipes").exists():
        shutil.rmtree(project / "recipes")
    shutil.copytree(ROOT / "adaptive-downloads/bakery",project,dirs_exist_ok=True)
    files = project / "recipes/toolchain/files"
    files.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(CACHE / "runtime.tar.gz",files / "runtime.tar.gz")
    for name in ("id_rsa.pub","ca.crt"):
        shutil.copyfile(CACHE / "keys" / name,files / name)
    dbus = Path(tools()["runtime"]) / "share/dbus-1/system.d/de.pengutronix.rauc.conf"
    shutil.copyfile(dbus,files / "rauc-dbus.conf")
    env = dict(os.environ,DOCKER="podman",RUGIX_DEV="true",RUGIX_BAKERY_IMAGE=BAKERY_IMAGE,
               RUGIX_CACHE_VOLUME="rugix-benchmarks-native")
    execute(["./run-bakery","bake","image","benchmark-amd64","--release-version",
             "20250701000000","--source-date",SOURCE_DATE],cwd=project,
             log=CACHE / "logs/bake-native.log",env=env)
    save_json(CACHE / "native-image.json",dict(bytes=image.stat().st_size,
              sha256=digest(image),bakery_image=BAKERY_IMAGE,source_date=SOURCE_DATE,
              runtime_archive_sha256=tools()["runtime_archive_sha256"], inputs=inputs))
    return image

def config(plan,workload: str,*,prepared=True):
    qemu = shutil.which("qemu-system-x86_64")
    if qemu is None:
        raise RuntimeError("Run in the pinned Nix development shell to provide QEMU")
    if not os.access("/dev/kvm",os.R_OK|os.W_OK):
        raise RuntimeError("Native timing requires usable /dev/kvm")
    share = Path(qemu).resolve().parents[1] / "share/qemu"
    firmware_code = Path(os.environ.get("RUGIX_OVMF_CODE_AMD64",share / "edk2-x86_64-code.fd"))
    firmware_vars = Path(os.environ.get("RUGIX_OVMF_VARS_AMD64",share / "edk2-i386-vars.fd"))
    if prepared:
        golden = CACHE / "golden" / workload
        drives = [Drive(file=golden / f"drive{n}.qcow2",format="qcow2",interface="virtio",overlay=True)
                  for n in (0,1)]
        firmware_vars = golden / "pflash1.raw"
    else:
        drives = [
            Drive(file=CACHE / "projects/native/build/benchmark-amd64/system.img",
                  format="raw",interface="virtio",overlay=True,size="40G"),
            Drive(file=CACHE / "disks" / (workload+".raw"),
                  format="raw",interface="virtio",overlay=True),
        ]
    return VMConfig(arch="x86_64",memory=plan.memory_mib,smp=plan.vcpus,drives=drives,
        pflash=[Pflash(file=firmware_code,readonly=True),Pflash(file=firmware_vars,readonly=False)],
        extra_args=["-device","virtio-rng-pci"])
