# hopsakee-server

Scripts and setting files for Hopsakee's Hetzner server. So I can easily start and stop this without needing to do a lot of manual work.

# Prerequisites

- An account at Hetzner
- SSH key registered at Hetzner
- An Hetzner API-key
- A DNS-server via OVHcloud

## With warning

The following items are also needed, but in these cases the code will give a warning if they are missing or wrong.


# The overview

1. Connect to the Hetzner API client

To do that, we need to create an API key at the Hetzner website and use that API key in our `.env` file. We use the `hcloud` python package from Hetzner for this.

2. Create the firewall

There are two options to do that:

- On the virtual machine itself
- Handled by Hetzner

We decided to do it by using the Hetzner way, so that's why we can set up the firewalls now. That means we should use the object `FireWallRule` from the `hcould` python package and create a FireWallRule for every port we want to open.

3. Create the actual server

This step is the main part and will contain:

- A YAML-file for the settings. We will use the "validate" function to check it before we use it with the hetzner package for Python.
    - with reference to the firewall rules set up on hetzner
    - with the ssh key
    - installing docker
    - creating the Docker network so the docker containers can talk over that network to each other, shielded from the internet
    - clone this repo onto the server
    - all the other things I want to install and settings I want to set.

4. NGINX + Certbot

A Docker Compose that runs NGINX + Certbot together, sharing volumes for SSL certificates and ACME challenges. This is a separate compose file from the app compose files.

5. Run the docker compose files using `systemd` services

For all the docker containers we want, we need to create Docker Compose files we want to run on that server when we restart or rebuild the server.
The book strongly recommends wrapping each docker compose up/down in a systemd service, so containers come back up after a reboot. That's the create-docker-compose-service.sh pattern.

# 1. Connect to the Hetzner API client

```python
from hcloud import Client
client = Client(token=<API-key>)
```

# 2. Create the firewall

## Parts

- HTTP (port 80)
- HTTPS (port 443)
- SSH (port 22) — optionally restricted to your IP only

# 3. Create the server

## Parts

- Ubuntu 24.04 LTS
- x86 architecture (better compatibility than ARM)
- Small size like CPX11 (2 CPU, 2GB RAM) — can scale up later
- Attach your SSH key
- Attach the firewall you created
- Give it a meaningful hostname (e.g., pyprod-host)

## Steps

### create ssh-key pair

```bash
ssh-keygen -t ed25519 -C "tps_si" -f ~/.ssh/tps_si
```

Upload the public key to Hetzner

```python
pubkey = Path('~/.ssh/tps_si.pub').expanduser().read_text().strip()
client.ssh_keys.create(name='tps_si', public_key=pubkey)
```

Check if pub-key is available

```python
client.ssh_keys.get_by_name('tps_si')
```

### set firewall using Hetzner firewall

```python
from hcloud.firewalls import FirewallRule

rules = [
    FirewallRule(direction='in', protocol='tcp', port='22', source_ips=['0.0.0.0/0', '::/0']),
    FirewallRule(direction='in', protocol='tcp', port='80', source_ips=['0.0.0.0/0', '::/0']),
    FirewallRule(direction='in', protocol='tcp', port='443', source_ips=['0.0.0.0/0', '::/0']),
]
client.firewalls.create(name='tps-firewall', rules=rules)
```

> Note: Restricting SSH (port 22) to only your IP for extra security.

### create the YAML file for server setup

We place all YAML and config files in the `config` folder.

We validate the server YAML using a json validate scheme. The validation works in three steps:

1. **Fetch the schema**: Downloads the official cloud-init JSON schema from GitHub — this defines what fields are valid in a cloud-init file

2. **Parse your YAML**: `yaml.load()` converts your YAML text into a Python dictionary

3. **Validate**: `jsonschema.validate()` checks if your dictionary matches the schema rules — if something's wrong (typo, invalid field), it raises an error

It's like spell-check but for cloud-init structure.

```python
def cc_validate(d: str) -> None:
    "Validate cloud-init YAML string against the official cloud-init JSON schema."
    vsc = xget('https://raw.githubusercontent.com/canonical/cloud-init/main/cloudinit/config/schemas/versions.schema.cloud-config.json').text
    validate(yaml.load(d, Loader=yaml.FullLoader), schema=json.loads(vsc))

cinit_content = Path('tps_cloud_init.yaml').read_text()
cc_validate(cinit_content)
```

### Find location to place server

```python
[(dc.name, dc.description) for dc in client.datacenters.get_all()]
```

Hetzner has a speed test page: speed.hetzner.de

### Decide on server type

Start small, for example CPX11: 2 CPU, 2GB RAM.

### Create the server

```python
sshkey = client.ssh_keys.get_by_name('tps_si')
firewall = client.firewalls.get_by_name('tps-firewall')

cinit_content = '#cloud-config\n' + Path('tps_cloud_init.yaml').read_text()

svr_r = client.servers.create(
    name='tps-server',
    server_type=ServerType(name='cpx11'),
    image=Image(name='ubuntu-24.04'),
    location=loc,
    ssh_keys=[sshkey],
    firewalls=[firewall],
    user_data=cinit_content
)
svr_r
```

To check the ip4-adress

```python
svr = svr_r.server
svr.public_net.ipv4.ip
```