import os
import subprocess

from pathlib import Path
from hcloud import Client
from hcloud.servers.client import BoundServer
from hcloud.firewalls import FirewallRule, BoundFirewall

def _check_ssh(name: str):
    """Check if private ssh-key of given name is available."""
    if not (Path.home() / '.ssh' / name).exists():
        raise FileNotFoundError(f"""
    There is no SSH-key with the name {name} create one.
    `ssh-keygen -t ed25519 -f ~/.ssh/{name}`
    and place the `{name}.pub` on the server.""")


def _setup_firewall(cli: Client, name: str, rules: list[FirewallRule]):
    if not isinstance(cli.firewalls.get_by_name(name), BoundFirewall):
        cli.firewalls.create(name='tps-firewall', rules=rules)


def create_hetzner_client(keyname: str):
    """Loads key from .env file of given keyname"""
    try:
        hkey = os.environ[keyname]
    except KeyError as e:
        print(f"The key {e} does not exist")
        raise

    return Client(token=hkey)

def setup_hetzner_server(
        cli: Client, # Hetzner client
        fname: str, # Name of Hetzner firewall
        frules: list[FirewallRule], # List of Firewall rules
        ):
    _setup_firewall(cli, fname, frules)
    
    pass

def remote(cmd: str, svr: BoundServer,  sshname: str, user: str ='ubuntu') -> None:
    """Sent bash commands to the remote server"""
    # TODO This check is on every remote call, make more efficient
    _check_ssh(sshname)
    ip = svr.public_net.ipv4.ip
    subprocess.run(f"ssh -i {Path.home() / '.ssh' / sshname} {user}@{ip} '{cmd}'", shell=True)

if __name__ == "__main__":
    cli = create_hetzner_client('HETZNER_API_KEY')
    frules = [
        FirewallRule(direction='in', protocol='tcp', port='22', source_ips=['0.0.0.0/0', '::/0']),
        FirewallRule(direction='in', protocol='tcp', port='80', source_ips=['0.0.0.0/0', '::/0']),
        FirewallRule(direction='in', protocol='tcp', port='443', source_ips=['0.0.0.0/0', '::/0']),
    ]
    fname = "tps-firewall"
    svr = setup_hetzner_server(cli, fname, frules)