# Physical-Device Secure Tunnel Setup (Phase 11.A, restructured into the 3-terminal sequence for Phase 12.7)

**This section is a command template for YOU to run on YOUR local machine
(the one with the phone attached via USB).** Nothing here was or can be
executed from this remote cluster session -- there is no path from
`piai-cluster`/`n10` to your local machine or your phone.

The backend is **not** exposed to the internet. It stays bound to
`127.0.0.1:8000` on the GPU node (`n10`), reachable only via an SSH tunnel
you control.

## Confirmed from this session (real, not assumed)

- The GPU node `n10` has `sshd` active and is directly SSH-reachable **from
  the cluster login node** with your existing key (`ssh n10` succeeded with
  no password prompt from the login node in this session).
- The backend was run as: `python -m uvicorn backend.main:app --host
  127.0.0.1 --port 8000`, on `n10`, inside SLURM job 2635 (`srun --jobid=2635
  --overlap ...`).

## Structure

```
Android app (127.0.0.1:8000)
  -> adb reverse tcp:8000 tcp:8000
  -> your local PC (127.0.0.1:8000)
  -> ssh -L (local port forward), via ProxyJump through the cluster login node
  -> n10 (127.0.0.1:8000, where uvicorn is listening)
```

## Commands (replace `<USER>` and `<CLUSTER_LOGIN_HOST>` with your real
values -- `<USER>` is your cluster username, e.g. `team_c1`;
`<CLUSTER_LOGIN_HOST>` is whatever hostname/IP you already use for your
existing VS Code Remote-SSH connection to this cluster)

**1. On your local PC**, open an SSH tunnel that hops through the login
node to `n10`:

```bash
ssh -N \
  -L 127.0.0.1:8000:127.0.0.1:8000 \
  -J <USER>@<CLUSTER_LOGIN_HOST> <USER>@n10
```

Leave this running in its own terminal (it produces no output when
working). If your SSH config already has a `Host` alias for the cluster
(the one VS Code Remote-SSH uses), you can use that alias in place of
`<USER>@<CLUSTER_LOGIN_HOST>`.

**If `-J` (ProxyJump) to `n10` is rejected** (some clusters block direct SSH
to compute nodes from outside an active job context even though the login
node itself can reach it): first confirm you still hold a running
allocation on `n10` (`squeue -u <USER>` from the login node), since compute
node SSH access is commonly gated on having an active job there. Do not
work around this by binding the backend to `0.0.0.0` or a public interface
-- ask before changing the tunnel topology if the direct hop doesn't work.

**2. Confirm the tunnel is up** (from your local PC, in a second terminal):

```bash
curl -s http://127.0.0.1:8000/api/v1/verification/qwen7b/health
```

Should return `{"success":true,...,"data":{"model_id":"Qwen/Qwen2.5-VL-7B-Instruct","loaded":true,...}}`.

**3. With the phone connected via USB debugging**, reverse-forward the
same port from the phone to your local PC:

```bash
adb reverse tcp:8000 tcp:8000
adb reverse --list
```

`adb reverse --list` should show `host-...  tcp:8000 tcp:8000`.

**4. Run the Flutter app pointed at localhost** (which now resolves,
via the two hops, to `n10`'s backend):

```bash
cd frontend
flutter devices                      # find your <DEVICE_ID>
flutter run -d <DEVICE_ID> \
  --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## Notes

- The backend's default hardcoded fallback for physical devices is
  `http://192.168.0.73:8000` (`frontend/lib/services/api_client.dart`) --
  a LAN IP unrelated to this cluster. The explicit `--dart-define` above
  overrides it; without the override, the app will try to reach that
  unrelated address and fail.
- No password, token, or key content is requested or should be pasted into
  this session -- run all of the above locally.
- If the backend needs restarting on `n10` between sessions, ask this
  session to do it via `srun --jobid=<jobid> --overlap ...` (it stays bound
  to `127.0.0.1`, never a public interface) -- do not start a second
  competing instance; check `ss -ltnp | grep 8000` on `n10` first.
