# LiteLLM database ownership

The working Aiven service has a dedicated `litellm` database. Its upstream-managed
objects are in `public`, owned by `litellm`; the schema-only inspection on
23 October 2026 found 91 relations. No application records were exported.

Use the pinned official LiteLLM migration image and the separate migration job
defined in [the LiteLLM infrastructure](../../../infra/litellm/README.md).
Prisma owns this schema. Do not apply Scanner/Momentum baselines or Liquibase here,
move vendor tables into application schemas, or regenerate vendor migrations in
this directory. Credentials and encrypted provider records remain in their existing
database and Secret Manager; recovery requires the original encryption salt.
