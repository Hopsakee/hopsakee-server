# Improvements — follow-ups after the pkw-web 502 incident

Context: On 2026-04-15, `datalab-knowledge.hopsakee.top` returned 502 after a successful-looking `client-deploy.sh` run. Root cause: the `pkw-web` container crash-looped because its Dockerfile created `appuser` with `--no-create-home`, leaving `$HOME=/home/appuser` nonexistent. At container start, `uv run main.py` tried to write to `$HOME/.cache/uv` and got EACCES, so the process exited. `docker compose up -d` returned 0 anyway (it only checks the container was *created*, not that it stayed running), so the deploy log showed success while the site was dead.

That specific bug is fixed (one-line change in `pkw-web/Dockerfile`). The items below are the *related* issues exposed by the incident — improvements worth making while the context is fresh.

---

## 1. Standardize the non-root user pattern across all app Dockerfiles

**Why:** pkw-web correctly tried to drop root privileges (good defense-in-depth: limits blast radius if the app gets RCE'd via NiceGUI/Quasar/a dependency). infoflow doesn't drop privileges at all — it runs as root, which is why it was unaffected by the same bug class. We should do the *good* thing (non-root) everywhere, and do it *correctly* (with a working home dir).

**The pattern** — paste into every app Dockerfile, right after the `uv sync` lines and before `EXPOSE`/`CMD`:

```dockerfile
# Create unprivileged user with a real home dir and fixed UID/GID
RUN groupadd --system --gid 1001 appuser \
 && useradd  --system --uid 1001 --gid appuser --create-home --shell /usr/sbin/nologin appuser \
 && chown -R appuser:appuser /app
USER appuser
```

**Four things this does that the original pkw-web block didn't:**

1. `--create-home` — gives `$HOME=/home/appuser` so `uv` (and anything using XDG dirs: pip, poetry, requests, huggingface_hub, etc.) has a writable cache. This is the flag whose absence caused the 502.
2. Fixed UID/GID (1001) — reproducible across rebuilds; predictable file ownership if a volume is ever mounted writable. Without this, each rebuild can get a different UID, which matters the moment you bind-mount a writable host dir.
3. `chown -R appuser:appuser /app` — source was `COPY`'d as root, so `/app` is root-owned. If the app writes *anywhere* under `/app` at runtime (nicegui's `.nicegui/` session store, a generated SQLite, logs, a graphviz PNG), it fails the same way uv did. Chowning the workdir prevents a whole family of future "why is my app crashing" bugs.
4. `/usr/sbin/nologin` shell — belt-and-suspenders. A compromised process inside the container can't spawn an interactive shell via `su - appuser`.

---

## 2. Apply the pattern to infoflow (after a one-command sanity check)

infoflow currently runs as root. Before switching it to appuser, verify it doesn't rely on writes to root-only paths at runtime:

```bash
ssh -i ~/.ssh/sledge_wsl ubuntu@hopsakee.top \
  'docker diff infoflow | grep -v "^D " | head -40'
```

`docker diff` lists every file added/changed inside the running container versus the image. Expected safe outcomes:
- Writes under `/tmp` or `/root/.cache` → the pattern above handles them (appuser's `/tmp` is writable; cache moves to `/home/appuser/.cache`).
- Writes under `/app/...` → handled by the `chown -R /app` line.

Unsafe outcome requiring extra work:
- Writes under `/var/log`, `/etc`, or some absolute path outside `/app`/`/tmp`/`/home/appuser` → those paths would need to be made appuser-writable explicitly (usually by creating them in the Dockerfile and `chown`-ing them). Unlikely for this app, but check.

If the diff is clean, apply the same snippet to `infoflow/Dockerfile`.

---

## 3. Upgrade pkw-web's fix to the standard pattern

The current pkw-web fix is minimal (`adduser --disabled-password --gecos ""` — drops `--no-create-home`). It works, but it uses the friendlier `adduser` wrapper with a dynamic UID and no `chown /app`. For consistency with infoflow once #2 is done, replace pkw-web's user-creation line with the same snippet from #1. Same security posture, predictable UID, future-proofed against `/app` writes.

---

## 4. Make silent crash-loops fail the deploy loudly

**Why:** The incident's real stinger was that `deploy-pkwweb.sh` printed "✅ pkw-web deployed successfully" while the container was actually restarting every 5 seconds. `docker compose up -d` exits 0 as soon as the container is *created*; it doesn't wait for the process inside to stay alive. Same failure mode will hit any future app.

**Fix — two parts:**

**(a) Add a healthcheck to each app's compose.yaml.** For pkw-web (`config/pkw-web/compose.yaml`):

```yaml
services:
  pkw-web:
    # ...existing fields...
    healthcheck:
      test: ["CMD", "wget", "-q", "-O-", "http://localhost:8080/"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 15s
```

`start_period` gives the app time to boot before failures count. `wget` is present in the `trixie-slim` base image already; no new dependency.

**(b) After `docker compose up --build -d`, block until the container is actually running.** Replace the last line of each `deploy-*.sh` with a small wait loop:

```bash
docker compose up --build -d

# Wait up to 30s for the container to become/stay running
svc=$(docker compose ps --services | head -1)
for i in $(seq 1 15); do
  state=$(docker inspect -f '{{.State.Status}}' "$(docker compose ps -q "$svc")" 2>/dev/null || echo missing)
  [ "$state" = "running" ] && break
  sleep 2
done

if [ "$state" != "running" ] || docker inspect -f '{{.State.Restarting}}' "$(docker compose ps -q "$svc")" 2>&1 | grep -q true; then
  echo "❌ $svc is not healthy (state=$state). Last logs:"
  docker compose logs --tail 30 "$svc"
  exit 1
fi
```

With this in place, `server-deploy.sh`'s `deploy_app` wrapper will see a real non-zero exit and print "❌ pkw-web failed — skipping" when — not long after — the next crash-loop bug ships.

This is also the single most useful change in the list, because it prevents the *class* of failure ("deploy looked green, site was dead") rather than fixing one instance of it.

---

## 5. (Optional) Consider a shared base image once 3+ apps exist

If steps 1–3 leave you pasting the same `groupadd`/`useradd`/`chown`/`USER` block into every Dockerfile, it's worth extracting once you have three or more apps on the server:

```dockerfile
# hopsakee-server/base/Dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim
RUN groupadd --system --gid 1001 appuser \
 && useradd  --system --uid 1001 --gid appuser --create-home --shell /usr/sbin/nologin appuser
WORKDIR /app
```

Publish as `ghcr.io/hopsakee/uv-appuser-base:python3.12`, then each app's Dockerfile becomes:

```dockerfile
FROM ghcr.io/hopsakee/uv-appuser-base:python3.12
COPY pyproject.toml uv.lock .
RUN --mount=type=cache,target=/root/.cache uv sync --no-install-project
COPY --chown=appuser:appuser . .
RUN --mount=type=cache,target=/root/.cache uv sync
USER appuser
EXPOSE 8080
CMD ["uv", "run", "main.py"]
```

Only worth the indirection at 3+ apps. For now, the copy-paste snippet in #1 is fine.

---

## Suggested order

1. Deploy step 4 (healthcheck + wait loop) first — this prevents the next silent failure regardless of which app it happens in.
2. Then step 2 (infoflow to appuser) — biggest outstanding security delta.
3. Then step 3 (unify pkw-web to the standard snippet) — cosmetic consistency.
4. Revisit step 5 when you have a third app.
