# Oracle A1 hunt

[![hunt](https://github.com/Ch1mpleo/oracle-a1-hunt/actions/workflows/hunt.yml/badge.svg)](https://github.com/Ch1mpleo/oracle-a1-hunt/actions/workflows/hunt.yml)

Tries to claim an Oracle Always Free Ampere A1 instance in `ap-singapore-1`
every 10 minutes, from GitHub Actions.

## What it asks for

`VM.Standard.A1.Flex`, tries 1 OCPU / 6 GB first, then 2 OCPU / 12 GB; override
the ordered candidates with `SHAPE_CONFIGS="1x6,2x12"`. Ubuntu 24.04 ARM, 50 GB boot, named
`openbot-vps`. Reuses the `openbot-vcn` / `openbot-subnet` network.

## Notifications

- Status comment on the `Oracle hunt status` issue at 08:00, 14:00 and 20:00
  Saigon time, with the last attempt's age; a missing comment means the status
  job stopped.
- The badge above shows the latest hunt result at a glance.
- New issue mentioning `@Ch1mpleo` when the instance is up, with its IP.
- A failed run exits non-zero, so GitHub reports it.
- Optional chat ping when `OPENBOT_WEBHOOK_SECRET` is set.

## Secret

One: `OCI_PRIVATE_KEY`, the PEM of the OCI API signing key. Until it exists,
each run no-ops with a warning instead of failing.

## Stopping it

Disable `hunt.yml` and `status.yml` in the Actions tab. An instance that is
already running stays up until it is terminated in the OCI console.
