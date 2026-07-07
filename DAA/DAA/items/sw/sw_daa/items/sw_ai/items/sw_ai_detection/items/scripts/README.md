# DVC NAS Push Setup

Steps required for any new machine to be able to `dvc push` to the shared NAS remote.

## 1. Add local group with GID 1003

```bash
sudo groupadd -g 1003 dvc_users
```

## 2. Add your user to the group

```bash
sudo usermod -aG 1003 <your_username>
```

## 3. Set umask so new directories are group-writable

Add to `~/.bashrc`:

```bash
echo "umask 002" >> ~/.bashrc
source ~/.bashrc
```

## 4. Re-login or apply group change in current session

```bash
newgrp dvc_users
```

Or log out and log back in.

## 5. Verify

```bash
id
# Should show 1003(dvc_users) among your groups

umask
# Should show 0002
```

## 6. Push

```bash
uv run dvc push
```

It should be noticed that the NAS must be mounted before pushing.
