# flex-domain

An example of how a public sector service journey could be exposed as a set of **symmetrical API endpoints** (request and response schemas are identical), written as a domain for [flex](https://github.com/govuk-once/flex) — GOV.UK serverless platform for building service domains on AWS CDK and TypeScript.

This sits within the broader [Agentic Legibility](../README.md) project, which explores serialising public sector workflows so they can be interpreted and driven by agents rather than only by a human clicking through a browser journey.

## The example journey

The domain models a driving-licence "change of address" journey (DVLA),
as four steps, each its own route:

| Route | Purpose |
|---|---|
| `POST /choose-address-entry-method` | Choose whether to look up an address by postcode or enter it manually |
| `POST /find-address-by-postcode` | Submit/receive an address found via postcode lookup |
| `POST /enter-address-manually` | Submit/receive a manually entered address |
| `POST /confirm-new-address` | Confirm the new address for the record |

## Layout

```
domain.config.ts            # flex domain definition: routes, resources, integrations
src/schemas/dvla-address.ts # zod schemas shared between request and response per route
src/handlers/v0.1/          # one handler per route, one route per folder
src/data/store.ts           # mock driver/address record used in place of a real backend
```

`domain.config.ts` is read by the `@flex/sdk` `domain()` builder to produce the `config`, `route`, and `routeContext` used by each handler. Handlers are plain flex route functions — see `src/handlers/v0.1/*/post.ts` — that read `body`, log via the injected `logger`, and return `{ status, data }`.

Handlers currently return data from the static `DRIVER` fixture in `src/data/store.ts` rather than calling a real DVLA integration — this is a scaffold for illustrating the domain/route/schema pattern, not a working integration.

## Commands

```bash
pnpm tsc          # type-check
pnpm lint         # eslint, zero warnings allowed
pnpm test         # unit tests (vitest)
```

## Related

- [flex](https://github.com/govuk-once/flex) — the platform this domain is built on
- [Agentic Legibility](../README.md) — the parent project this example supports
