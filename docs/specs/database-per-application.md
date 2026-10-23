# Database ownership

The current architecture and operator commands are maintained in the
[domain database guide](../../database/README.md). Each application has one database,
with separate schemas for analysis, ADK sessions, and Liquibase metadata.

The schema-only Aiven snapshot dated 23 October 2026 is the reconstruction reference.
The completed shared-to-domain cutover and its superseded installation paths are
available in Git history, not as current deployment instructions.
