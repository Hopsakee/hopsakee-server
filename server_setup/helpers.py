import os
import subprocess

from pathlib import Path
from hcloud import Client
from hcloud.servers.client import BoundServer

hkey = os.environ['HETZNER_API_KEY']
cli = Client(token=hkey)

if not (Path.home() / '.ssh' / 'tps_si').exists():
    raise FileNotFoundError("""
There is no SSH-key with the name 'tps_si' create one.
`ssh-keygen -t ed25519 -f ~/.ssh/tps_si`
and place the `tps_si.pub` on the server.""")


def remote(cmd: str, svr: BoundServer,  user: str ='ubuntu') -> None:
    """Sent bash commands to the remote server"""
    ip = svr.public_net.ipv4.ip
    subprocess.run(f"ssh -i {Path.home() / '.ssh/tps_si'} {user}@{ip} '{cmd}'", shell=True)
