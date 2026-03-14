# Changes & Lessons Learned — hopserver.py & cloud-init

This document describes all issues encountered while building the Hetzner server provisioning script (`server_setup/hopserver.py`) and the cloud-init configuration (`config/tps_cloud_init.yaml`), along with the fixes applied.

---

## 1. Relative file paths break depending on working directory

**Problem:** Config files were referenced with relative paths like `../config/tps_cloud_init.yaml`. This only works when running the script from inside `server_setup/`, not from the project root.

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: '../config/tps_cloud_init.yaml'
```

**Fix:** Use `Path(__file__).resolve().parent.parent` to derive the repository root from the script's own location. This works regardless of where the script is invoked from.

```python
# Before
config_yaml = Path('../config/tps_cloud_init.yaml')
settings_yaml = Path('../config/settings.yaml')

# After
repo_root = Path(__file__).resolve().parent.parent
config_yaml = repo_root / 'config' / 'tps_cloud_init.yaml'
settings_yaml = repo_root / 'config' / 'settings.yaml'
```

**Lesson:** Never use relative paths (`../`) in scripts. Always resolve paths relative to the script file itself using `__file__`, so the script works from any working directory.

---

## 2. Hetzner API requires CIDR notation for IPs

**Problem:** The `IP_ALLOW` environment variable contained a bare IP address (e.g. `1.2.3.4`), but the Hetzner firewall API requires CIDR notation (e.g. `1.2.3.4/32`).

**Error:**
```
hcloud._exceptions.APIException: invalid input in field 'rules[].source_ips' (invalid_input)
```

**Fix:** Append `/32` to each IP address. Also added support for multiple comma-separated IPs in the environment variable.

```python
# Before
FirewallRule(direction='in', protocol='tcp', port='22', source_ips=[os.environ["IP_ALLOW"]])

# After — supports multiple comma-separated IPs, appends /32
FirewallRule(direction='in', protocol='tcp', port='22',
    source_ips=[ip.strip() + '/32' for ip in os.environ["IP_ALLOW"].split(',')])
```

**Lesson:** The Hetzner API always expects IP addresses in CIDR notation. `/32` means "this single IP address". Set `IP_ALLOW` as a comma-separated list, e.g. `IP_ALLOW=1.2.3.4,5.6.7.8`.

---

## 3. Hetzner API requires `Location` object, not a string

**Problem:** The `location` parameter in `cli.servers.create()` was passed as a plain string from the YAML config, but the hcloud library expects a `Location` object.

**Error:**
```
AttributeError: 'str' object has no attribute 'id_or_name'
```

**Fix:** Import `Location` from the hcloud library and wrap the string.

```python
from hcloud.locations import Location

# Before
location=ycs['location'],

# After
location=Location(name=ycs['location']),
```

**Lesson:** The hcloud Python library requires typed objects for `server_type`, `image`, and `location` — not raw strings. Use `ServerType(name=...)`, `Image(name=...)`, and `Location(name=...)` respectively. Note: `ssh_keys` and `firewalls` can use the `Bound*` objects returned by `get_by_name()` directly.

---

## 4. SSH falls back to password prompt during cloud-init

**Problem:** While polling `cloud-init status` via SSH, the script would hang waiting for a password input. This happened because cloud-init hadn't finished setting up the SSH authorized keys yet, so key-based auth failed and SSH fell back to asking for a password.

**Fix:** Add `-o BatchMode=yes` to the SSH command. This disables interactive password prompts, causing SSH to fail cleanly when key auth isn't ready. The `except` block catches the failure and the polling loop retries.

```python
# Before
cmd = f"ssh -i ~/.ssh/{sshname} -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@{ip} 'cloud-init status'"

# After
cmd = f"ssh -i ~/.ssh/{sshname} -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes ubuntu@{ip} 'cloud-init status'"
```

**Lesson:** Always use `-o BatchMode=yes` for non-interactive SSH commands in scripts. It prevents the script from hanging on unexpected password prompts.

---

## 5. Cloud-init polling loop used iteration count instead of wall-clock time

**Problem:** The timeout check `if c > 200` counted loop iterations, not seconds. Each iteration could take up to 10 seconds (SSH timeout) + 0.2 seconds (sleep), so 200 iterations could take up to ~2000 seconds instead of the intended ~200 seconds.

**Fix:** Use `time.time()` for a proper wall-clock timeout, and increase the sleep interval from 0.2s to 2s (polling every 200ms is unnecessarily aggressive for a process that takes minutes).

```python
# Before
c = 0
while (status := check_cloud_init(ip, sshname)) != 'status: done':
    if c > 200: raise TimeoutError(...)
    c += 1
    sleep(.2)

# After
timeout = 300
start = time.time()
c = 0
while (status := check_cloud_init(ip, sshname)) != 'status: done':
    if status and 'error' in status: raise RuntimeError(f"Cloud-init failed: {status}")
    elapsed = time.time() - start
    if elapsed > timeout: raise TimeoutError(f"Cloud-init stuck after {elapsed:.0f}s at: {status}")
    print(f"\r{spinner[c % 4]} Waiting... ({elapsed:.0f}s)", end='', flush=True)
    c += 1
    sleep(2)
```

**Lesson:** When implementing timeouts in polling loops, always use wall-clock time, not iteration counts. The actual duration of each iteration can vary wildly depending on network timeouts and other factors.

---

## 6. Cloud-init polling loop didn't detect errors

**Problem:** The `while` loop only checked for `status: done`. If cloud-init finished with `status: error`, the loop kept polling until the timeout — wasting up to 5 minutes before reporting the failure.

**Fix:** Check for `error` in the status string and raise immediately.

```python
if status and 'error' in status:
    raise RuntimeError(f"Cloud-init failed: {status}")
```

**Lesson:** Always check for error states in polling loops, not just the success condition. Fail fast when something goes wrong.

---

## 7. `cloud-init status --timeout` is not universally supported

**Problem:** During investigation in a notebook, `cloud-init status --wait --timeout 300` was tried, but the server's cloud-init version doesn't support the `--timeout` flag.

**Error:**
```
error: unrecognized arguments: --timeout 300
```

**Lesson:** The `--timeout` flag for `cloud-init status` was added in newer versions. Older versions only support `--wait` (`-w`). The polling approach in the script (calling `cloud-init status` repeatedly with a sleep) is more portable and works with all cloud-init versions.

---

## 8. `runcmd` runs as root — tools installed for ubuntu aren't available

**Problem:** The `uv tool install shell_sage` command in cloud-init's `runcmd` ran as root, but `uv` was installed for the `ubuntu` user (in `/home/ubuntu/.local/bin/`). Root doesn't have `uv` in its PATH.

**Error (from `/var/log/cloud-init-output.log`):**
```
('scripts_user', RuntimeError('Runparts: 1 failures (runcmd) in 1 attempted commands'))
```

**Fix:** Run the command as the ubuntu user with the full path to `uv`:

```yaml
# Before
- |
  # Install shellsage
  uv tool install shell_sage

# After
- |
  # Install shellsage
  sudo -u ubuntu -H bash << 'EOF'
  /home/ubuntu/.local/bin/uv tool install shell_sage
  EOF
```

**Lesson:** All `runcmd` commands execute as root by default. If a tool was installed for a specific user, you must either use `sudo -u <user>` to run as that user, or use the tool's full absolute path. Don't assume user-installed tools are in root's PATH.

---

## 9. `mkdir` with relative paths fails in cloud-init

**Problem:** `mkdir -p apps services config storage` used relative paths. During cloud-init, the working directory is not `/home/ubuntu` (it's typically `/root` or `/`), so the `ubuntu` user doesn't have write permission.

**Error:**
```
mkdir: cannot create directory 'apps': Permission denied
```

**Fix:** Use `$HOME` (or `~`) to create directories in the user's home:

```yaml
mkdir -p $HOME/apps $HOME/services $HOME/config $HOME/storage
```

**Lesson:** Never rely on the working directory in cloud-init `runcmd` scripts. Always use absolute paths or `$HOME`/`~` to reference user directories.

---

## 10. Heredocs and shell variable expansion in cloud-init

**Problem:** Using `$HOME` inside a heredoc (`<< EOF`) caused the *outer* shell (root) to expand the variable before passing it to the inner bash (ubuntu). Root's `$HOME` was empty/unset in the cloud-init context, resulting in paths like `/apps` instead of `/home/ubuntu/apps`.

**Error:**
```
mkdir: cannot create directory '/apps': Permission denied
```

**Fix:** Quote the heredoc delimiter (`<< 'EOF'`) to prevent variable expansion by the outer shell. The inner bash (running as ubuntu with `-H` setting `$HOME=/home/ubuntu`) then expands `$HOME` correctly.

```yaml
# Before — $HOME expanded by outer shell (root), resolves to empty/root
sudo -u ubuntu -H bash << EOF
mkdir -p $HOME/apps
EOF

# After — $HOME passed through to inner shell (ubuntu), resolves to /home/ubuntu
sudo -u ubuntu -H bash << 'EOF'
mkdir -p $HOME/apps
EOF
```

**Lesson:** In bash heredocs:
- `<< EOF` — variables like `$HOME` are expanded by the **outer** shell
- `<< 'EOF'` — variables are passed through literally and expanded by the **inner** shell

When using `sudo -u <user> -H bash << EOF` to run commands as a different user, always quote the delimiter (`<< 'EOF'`) if you want variables to resolve in the inner user's context.

---

## Debugging tip: Check cloud-init logs

When cloud-init reports an error, the status output only shows a generic failure message. To see which specific command failed and why, check the detailed log:

```bash
ssh -i ~/.ssh/<key> ubuntu@<ip> 'sudo tail -50 /var/log/cloud-init-output.log'
```

Note: This log requires `sudo` to read.
