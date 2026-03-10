
# Future improvements

- [ ] `_validate_cloud_config` fetches from the internet every time — consider caching the schema locally so it works offline and is faster.
- [ ] `setup_hetzner_server` does a lot — it sets up the firewall, checks SSH, validates config, and creates the server. That's fine for now, but worth noting.
- [ ] `cfile` prepends `#cloud-config` — smart, keeps your YAML file clean. But it assumes the file never already has that header — worth a quick check or a comment explaining why.
- [ ] `__main__` block — the firewall rules and sshname are hardcoded there. Eventually those probably belong in `settings.yaml` too.