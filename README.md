# Oracle A1 hunt

Tries to claim an Oracle Cloud **Always Free Ampere A1** instance in `ap-singapore-1`
every 15 minutes, from GitHub's servers instead of a laptop.

Oracle has no waitlist: capacity frees up at random and the API is the only way to
catch it. This repo is that API loop.

## What it asks for

| Setting | Value |
|---|---|
| Shape | `VM.Standard.A1.Flex`, 2 OCPU / 12 GB (inside the free 4 OCPU / 24 GB) |
| Boot volume | 50 GB |
| Image | Canonical Ubuntu 24.04 aarch64 |
| Region | `ap-singapore-1` |
| Name | `openbot-vps` |
| Network | reuses `openbot-vcn` / `openbot-subnet`, creates them only if missing |

## How it notifies you

1. **GitHub issue** mentioning `@Ch1mpleo` — that produces an email and a phone
   notification through the GitHub app, with the public IP. No setup needed.
2. **Chat message from OpenBot**, if `OPENBOT_WEBHOOK_URL` and
   `OPENBOT_WEBHOOK_SECRET` are set. The request is signed with
   HMAC-SHA256 over `<timestamp>.<delivery-id>.<body>`.

## Secrets

Set under *Settings → Secrets and variables → Actions*:

| Secret | Where it comes from |
|---|---|
| `OCI_TENANCY` | OCI console, tenancy OCID |
| `OCI_USER` | OCI console, user OCID |
| `OCI_FINGERPRINT` | the API key fingerprint, `1a:6b:...` |
| `OCI_REGION` | `ap-singapore-1` |
| `OCI_PRIVATE_KEY` | full PEM text of the API signing key |
| `OPENBOT_WEBHOOK_URL` | optional, the routine's URL |
| `OPENBOT_WEBHOOK_SECRET` | optional, the signing secret |

## Turning it off

Disable both workflows in the Actions tab, or delete the repo. An instance that
is already running keeps running until you terminate it in the OCI console.

## Security notes

- The private key grants full API access to the tenancy. GitHub stores it
  encrypted, and only workflow runs on `main` can read it.
- The repo is public on purpose: public repos get unlimited Actions minutes.
  Private repos would exhaust the 2,000 monthly minutes at this frequency.
- Triggers are `schedule` and `workflow_dispatch` only, so a pull request from a
  fork can never reach the secrets.
- Only `ssh_key.pub` is committed. The private half stays on the owner's machine
  at `~/.ssh/openbot_vps`.
