# Backend image builder

Independent Terraform root for the identity that builds backend images:
`market-scanner-adk`, `market-scanner-api`, `momentum-api` (repository
`market-scanner`) and the Momentum worker (repository `momentum`).

Without it, `gcloud builds submit` falls back to the project's default compute
service account, which holds `roles/editor` on the whole project. A malicious
build dependency would then inherit that access. This builder can only:

- read its staged sources (`storage.objectViewer` on its own bucket);
- push images to the two backend repositories (`artifactregistry.writer`);
- write build logs (`logging.logWriter`, the only project-level grant).

Staged sources are private and deleted after seven days.

## Apply

Run from the repository root and review the saved plan before applying it.

```sh
terraform -chdir=infra/backend-build init -backend-config=preprod.backend.hcl
terraform -chdir=infra/backend-build plan -out=build.tfplan
terraform -chdir=infra/backend-build apply build.tfplan
```

## Build an image

Submit from the application directory so its Dockerfile and ignore rules apply.
`gcloud` uses `.gcloudignore`, or `.gitignore` when it is absent; check that no
`.env` file is uploaded. Example for the Momentum worker:

```sh
gcloud builds submit apps/backend/momentum-adk \
  --project=preprod-deep-copy --region=europe-west1 \
  --config=infra/backend-build/cloudbuild.yaml \
  --substitutions=_IMAGE=europe-west1-docker.pkg.dev/preprod-deep-copy/momentum/worker \
  --service-account=projects/preprod-deep-copy/serviceAccounts/backend-builder@preprod-deep-copy.iam.gserviceaccount.com \
  --gcs-source-staging-dir=gs://preprod-deep-copy-backend-build-sources/source \
  --format='value(results.images[0].digest)'
```

| Application directory | `_IMAGE` |
| --- | --- |
| `apps/backend/market-scanner-adk` | `europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-adk` |
| `apps/backend/market-scanner-api` | `europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-api` |
| `apps/backend/momentum-api` | `europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/momentum-api` |
| `apps/backend/momentum-adk` | `europe-west1-docker.pkg.dev/preprod-deep-copy/momentum/worker` |

`momentum-api` may keep its own `infra/momentum-api/cloudbuild.yaml`; pass the
same `--service-account` and `--gcs-source-staging-dir` flags.
Record the resulting `sha256:...` digest in the deployment variables; never deploy a tag.

## Remove the default editor grant

Only after a successful build with this identity for each image above:

```sh
gcloud projects remove-iam-policy-binding preprod-deep-copy \
  --member=serviceAccount:660932163502-compute@developer.gserviceaccount.com \
  --role=roles/editor
```

Offline checks:

```sh
terraform -chdir=infra/backend-build fmt -check
terraform -chdir=infra/backend-build init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/backend-build validate
terraform -chdir=infra/backend-build test
```
