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

1. Connect to the Hetzner API client. 

To do that, we need to create an API key at the Hetzner website and use that API key in our `.env` file. We use the `hcloud` python package from Hetzner for this.

2. Create the firewalls.

There are two options to do that:

- On the virtual machine itself
- Handled by Hetzner

We decided to do it by using the Hetzner way, so that's why we can set up the firewalls now. That means we should use the object `FireWallRule` from the `hcould` python package and create a FireWallRule for every port we want to open.

3. Create the actual server.

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
