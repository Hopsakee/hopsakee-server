import os
import yaml, json
import subprocess

from httpx import get as xget
from pathlib import Path
from jsonschema import validate
from time import sleep

from hcloud import Client
from hcloud.images import Image
from hcloud.server_types import ServerType
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
        cli.firewalls.create(name=name, rules=rules)

def _validate_cloud_config(d: str):
    vsc = xget('https://raw.githubusercontent.com/canonical/cloud-init/main/cloudinit/config/schemas/versions.schema.cloud-config.json').text
    yd = yaml.load(d, Loader=yaml.FullLoader)
    validate(yd, schema=json.loads(vsc))
    return yd

def create_hetzner_client(keyname: str):
    """Loads key from .env file of given keyname"""
    try:
        hkey = os.environ[keyname]
    except KeyError as e:
        raise KeyError(f"The key {e} does not exist")

    return Client(token=hkey)

def setup_hetzner_server(
        cli: Client, # Hetzner client
        cfile: Path, # YAML-config file for server
        sfile: Path, # YAML-settings file for server type, location and image
        sshname: str, # Name of ssh-key
        fname: str, # Name of Hetzner firewall
        frules: list[FirewallRule], # List of Firewall rules
        recreate: bool = True, # Delete and recreate if already existing
        ) -> BoundServer:
    cc = '#cloud-config\n' + Path(cfile).read_text()
    ycc = _validate_cloud_config(cc)
    hname = ycc['hostname']
    x = cli.servers.get_by_name(hname)
    if x and recreate:
        x.delete()
        print(f"Deleted existing server {hname}")
    elif x and not recreate:
        print(f"Server with hostname {hname} already exists.")
        raise

    ycs = yaml.load(Path(sfile).read_text(), Loader=yaml.FullLoader)

    _setup_firewall(cli, fname, frules)
    firewall = cli.firewalls.get_by_name(fname)
    _check_ssh(sshname)
    sshkey = cli.ssh_keys.get_by_name(sshname)

    svr_r = cli.servers.create(
        name=hname,
        server_type=ServerType(name=ycs['servertype']),
        image=Image(name=ycs['image']),
        location=ycs['location'],
        ssh_keys=[sshkey],
        firewalls=[firewall],
        user_data=cc
    )

    # Wait for running
    svr = svr_r.server
    print("Waiting for new server to be created")
    c = 0
    while svr.status != 'running':
        if c > 250: raise TimeoutError(f"Server stuck at status: {svr.status}")
        svr.reload()
        spinner = ['|', '/', '-', '\\']
        print(f"\r{spinner[c % 4]} Waiting...", end='', flush=True)
        c += 1
        sleep(.2)
    
    ip = svr.public_net.ipv4.ip

    # Remove the "know_host", else the SSH security detects the server's host key is not the same
    # So it should be removed from "known_hosts" so the new server host key can be added.
    if x and recreate:
        subprocess.run(f'ssh-keygen -f ~/.ssh/known_hosts -R {ip}', shell=True, capture_output=True)

    print(f"Server running!\n\n`ssh -i ~/.ssh/tps_si ubuntu@{ip}`")
    print(f"\nWaiting for new server to be initialized")
    c = 0
    while (status := check_cloud_init(ip)) != 'status: done':
        if c > 600: raise TimeoutError(f"Cloud-init stuck at: {status}")
        spinner = ['|', '/', '-', '\\']
        print(f"\r{spinner[c % 4]} Waiting...", end='', flush=True)
        c += 1
        sleep(.2)
    return svr

def check_cloud_init(ip):
    cmd = f"ssh -i ~/.ssh/tps_si -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@{ip} 'cloud-init status'"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except: return None

def remote(cmd: str, svr: BoundServer,  sshname: str, user: str ='ubuntu') -> None:
    """Sent bash commands to the remote server"""
    # TODO This check is on every remote call, make more efficient
    _check_ssh(sshname)
    ip = svr.public_net.ipv4.ip
    subprocess.run(f"ssh -i {Path.home() / '.ssh' / sshname} {user}@{ip} '{cmd}'", shell=True)

def deploy_apps(svr: BoundServer, sshname: str) -> None:
    """Start the `deploy.sh` script on the server to deploy all the apps."""
    remote("bash ~/hopsakee-server/server_setup/deploy.sh", svr, sshname)

if __name__ == "__main__":
    cli = create_hetzner_client('HETZNER_API_KEY')
    config_yaml = Path('../config/tps_cloud_init.yaml')
    settings_yaml = Path('../config/settings.yaml')
    sshname = "tps_si"
    frules = [
        FirewallRule(direction='in', protocol='tcp', port='22', source_ips=['86.83.57.45']),
        FirewallRule(direction='in', protocol='tcp', port='80', source_ips=['0.0.0.0/0', '::/0']),
        FirewallRule(direction='in', protocol='tcp', port='443', source_ips=['0.0.0.0/0', '::/0']),
    ]
    fname = "tps-firewall"
    svr = setup_hetzner_server(cli, config_yaml, settings_yaml, sshname, fname, frules)
    deploy_apps(svr, sshname)
