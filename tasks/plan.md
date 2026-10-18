# Public frontend delivery plan

Specification: [public frontend](../docs/specs/public-frontend.md).

1. Bootstrap a reproducible standalone Next.js application and `just` commands.
2. Port the active landing design in bounded slices; replace account/newsletter
   actions with public documentation and scanner navigation.
3. Port public documentation without the account/IBKR credential journey.
4. Adapt report-v3 with validated data and an isolated IAM reader client.
5. Connect the public scanner display and cover failure/empty/data-quality states.
6. Add container, CI and Terraform-managed public Cloud Run deployment.
7. Show conclusion and public arbitration first, and keep detailed figures and
   macro analysis in keyboard-accessible disclosures. Preserve historical reports.
8. Run accessibility/responsive checks, review commit size and verify live behavior.

The maintainer requested landing work in the existing PR #12. Consolidate the
application slices there in dependency-ordered commits, each below 1,000 changed
lines excluding only the generated npm lockfile. Report lockfile size separately.
Cloud Run deployment remains a follow-up, outside the current landing/arbitration
review. Local fixture checks do not establish live synthesis quality.
Do not merge PRs automatically. Deploy only the reviewed and tested final image.
