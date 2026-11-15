# Oracle A1 hunt

Tries to claim an Oracle Always Free Ampere A1 instance in `ap-singapore-1`
every 15 minutes, from GitHub Actions.

## What it asks for

`VM.Standard.A1.Flex`, 2 OCPU / 12 GB, Ubuntu 24.04 ARM, 50 GB boot, named
`openbot-vps`. Reuses the `openbot-vcn` / `openbot-subnet` network.

## Notifications

- Daily status comment on the `Oracle hunt status` issue, 08:00 Saigon time.
- New issue mentioning `@Ch1mpleo` when the instance is up, with its IP.
- A failed run exits non-zero, so GitHub reports it.
- Optional chat ping when `OPENBOT_WEBHOOK_SECRET` is set.

## Secret

One: `OCI_PRIVATE_KEY`, the PEM of the OCI API signing key. Until it exists,
each run no-ops with a warning instead of failing.

## Stopping it

Disable `hunt.yml` and `status.yml` in the Actions tab. An instance that is
already running stays up until it is terminated in the OCI console.
