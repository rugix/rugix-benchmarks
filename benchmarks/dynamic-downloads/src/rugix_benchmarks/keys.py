"""Generate isolated signing, TLS and SSH identities for disposable test VMs."""
from __future__ import annotations

from .common import CACHE, execute

def prepare():
    directory = CACHE / "keys"
    directory.mkdir(parents=True,exist_ok=True)
    if not (directory / "id_rsa").exists():
        execute(["ssh-keygen","-q","-t","rsa","-b","2048","-N","","-C","rugix-benchmarks",
                 "-f",str(directory / "id_rsa")])
    if not (directory / "signer.crt").exists():
        execute(["openssl","req","-x509","-newkey","rsa:2048","-nodes","-days","365",
                 "-subj","/CN=Rugix Benchmark Test CA",
                 "-addext","basicConstraints=critical,CA:TRUE",
                 "-addext","keyUsage=critical,keyCertSign,cRLSign",
                 "-keyout",str(directory / "ca.key"),"-out",str(directory / "ca.crt")],
                 log=CACHE / "logs/pki-ca.log")
        execute(["openssl","req","-new","-newkey","rsa:2048","-nodes",
                 "-subj","/CN=Rugix Benchmark Bundle Signer",
                 "-keyout",str(directory / "signer.key"),"-out",str(directory / "signer.csr")],
                 log=CACHE / "logs/pki-signer.log")
        extensions = directory / "signer.ext"
        extensions.write_text("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=codeSigning\n")
        execute(["openssl","x509","-req","-in",str(directory / "signer.csr"),
                 "-CA",str(directory / "ca.crt"),"-CAkey",str(directory / "ca.key"),
                 "-CAcreateserial","-days","365","-extfile",str(extensions),
                 "-out",str(directory / "signer.crt")],log=CACHE / "logs/pki-sign.log")
    if not (directory / "server.crt").exists():
        execute(["openssl","req","-x509","-newkey","rsa:2048","-nodes","-days","365",
                 "-subj","/CN=Rugix Benchmark Origin",
                 "-addext","subjectAltName=IP:10.0.3.2",
                 "-addext","extendedKeyUsage=serverAuth",
                 "-keyout",str(directory / "server.key"),"-out",str(directory / "server.crt")],
                 log=CACHE / "logs/pki-tls.log")
    for path in directory.glob("*.key"):
        path.chmod(0o600)
    for path in directory.glob("*.crt"):
        path.chmod(0o644)
