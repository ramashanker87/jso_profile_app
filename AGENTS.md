# Project guide for contributors and coding agents

This file applies to the whole repository. Read it before making changes. Keep it
as the shared starting point for understanding, updating, and refactoring the
project. Detailed feature rules belong in the linked documents, not duplicated
here. Explicit user instructions take precedence over this guide.

## Start each task

1. Read this file and the relevant feature guide below.
2. Check `git status --short` and inspect the affected code and tests. Preserve
   existing user changes; do not reset or overwrite unrelated work.
3. Trace the behavior through UI, API client, handler, service, and storage as
   applicable. Check local/mock implementations as well as production adapters.
4. Make the smallest coherent change that satisfies the request. Preserve public
   contracts and stored data unless the task explicitly changes them.
5. Run the relevant checks, update affected documentation, and report what changed,
   what was verified, and any remaining limitation.

For a broad refactor, describe the intended scope and compatibility constraints
before editing. Continue routine work without repeatedly asking for permission.
Ask for missing information when it materially affects requirements or safety.

## What this application does

JSO Community Portal is a private community application with four areas:

- **Idea Incubation:** NeetoForm submissions, search, background synchronization,
  and private PDF previews/downloads.
- **Members:** an active-member directory with search, chapter/country/region
  filters, a country map, and verified members editing their own information.
- **Sambhav:** nine domains with three idea slots each, shared editing, member
  assignments, and PDF attachments.
- **Jobs:** shared job-opening links, short descriptions, and private candidate/job
  profile PDF attachments that approved users can add, download, and delete.

Production sign-in uses Cognito with Google or email/password. Users need the
`profile-library-users` group for application access. A directory entry alone
does not create or approve a login.

## Architecture and code map

Frontend: React 19, TypeScript, Vite, React Router, and Amplify authentication.
Backend: Python 3.12 AWS Lambda handlers, services, and storage adapters.
Infrastructure: Terraform, API Gateway HTTP API, Cognito, DynamoDB, private S3,
CloudFront, Secrets Manager, and CloudWatch.

Requests flow from browser API clients through API Gateway to the API Lambda.
Long-running synchronization runs in the worker Lambda; the browser polls job
status. Authorized file operations use temporary signed S3 links/forms.

| Location | Responsibility |
| --- | --- |
| `frontend/src/App.tsx` | Application routes; Members and Idea Incubation share list/detail pages |
| `frontend/src/pages/` | Page behavior and composition |
| `frontend/src/components/` | Reusable UI, editors, map, sync controls, and PDF views |
| `frontend/src/auth/` | Auth provider, route guard, and Cognito/local/demo clients |
| `frontend/src/services/` | API clients and browser mock implementation |
| `frontend/src/types/` | Frontend data contracts |
| `frontend/src/programs/sambhav.ts` | Sambhav program structure |
| `frontend/src/styles/main.css` | Shared styling |
| `backend/src/handlers/api.py` | API dispatch and application authorization |
| `backend/src/handlers/worker.py` | Background processing and sync continuation |
| `backend/src/handlers/` | Endpoint-specific request handling |
| `backend/src/services/` | Business rules, source adapters, file handling, and synchronization |
| `backend/src/repositories/` | Persistence and coordination adapters; some services also use tables directly |
| `backend/src/runtime.py` | Production dependency wiring and service construction |
| `backend/src/config.py` | Backend environment settings |
| `backend/src/sambhav_seed.json` | Backend Sambhav seed structure |
| `backend/local.py`, `backend/mock_neeto.py` | Local API and mock source server |
| `backend/tests/`, `frontend/tests/` | Regression tests and fixtures |
| `infrastructure/terraform/` | AWS resources, permissions, routes, and deployment variables |
| `scripts/` | Build, deploy, import, synchronization, and verification tools |

Keep business rules in services, transport handling in handlers/API clients, and
storage concerns in the existing adapters where practical. Follow nearby patterns;
do not introduce a new framework or broad abstraction for a small change.

## Behavior to preserve

Unless the requested change intentionally revises these rules:

- **Authorization:** API Gateway validates JWTs; the backend also enforces access
  tokens, client identity, group membership, and operation-specific permissions.
  UI guards alone are insufficient. Member self-edits require a verified login
  email matching the target record, checked against Cognito user attributes.
- **Member edits:** personal overrides in `SelfEdits` survive source sync. Do not
  overwrite them with imported data or write them back to NeetoForm.
- **Reconciliation:** source-owned members can be removed only after a complete,
  successful source read confirms absence. Idea Incubation does not automatically
  delete submissions missing from the source. These are different workflows.
- **Filtering and counts:** filter before pagination. The Members active count
  reflects all selected filters and search. Map counts respect search, chapter,
  and region while keeping the country distribution visible after country
  selection. Idea Incubation distinguishes `totalProfiles` from filtered `total`.
- **Member geography:** organizational region is manually assigned; do not infer
  it from country. Preserve the validation rules in the affiliation guide.
- **Sync correctness:** preserve deterministic profile IDs, revision checks,
  leases, checkpoints, duplicate-delivery handling, and older-update protection.
  An accepted webhook means queued work, not completed persistence. Verify raw
  webhook signatures before parsing or processing the payload.
- **Sambhav:** preserve domain/slot IDs, ordering, nine domains, three ideas per
  domain, and optimistic version checks. Coordinate frontend structure and
  backend seed changes. Preserve attachments during text edits and validate staged
  uploads before publishing. Current limits are 30 PDFs per idea and 20 MB per PDF.
- **Jobs:** job openings are distinct from synchronization jobs. Retain URL
  validation, duplicate protection, and explicit deletion confirmation. The
  application links to job websites; it does not scrape their content. Job uploads
  use private S3 staging and validated final copies, with owner-bound tickets and
  conditional metadata writes. Preserve partial-upload retries and legacy records
  without attachments. Current limits are 10 PDFs per job, 20 MB per PDF, and
  2,000 description characters.
- **Private files:** preserve private buckets, authorized short-lived links,
  download host restrictions, file validation, and safe object keys. Do not expose
  internal keys or private source URLs in public API payloads.
- **Search:** current directory queries scan records, then filter/sort/paginate.
  Do not describe this as indexed database search. A performance refactor must
  preserve complete results, counts, and pagination semantics.

## Development commands

Run from the repository root unless a command explicitly changes directory.
Prerequisites: Node.js 22.12+, npm, Python 3.12+ with venv, and make.

```bash
make setup                         # Install Python/npm dependencies; create missing frontend env
make dev                           # Frontend on http://localhost:5173
make test                          # Backend pytest and frontend Vitest
(cd frontend && npm run build)      # TypeScript check and production frontend build
./scripts/build-backend.sh          # Package Python Lambda dependencies and source
```

For a browser-only demo, explicitly select mock mode if existing environment
settings differ:

```bash
VITE_USE_MOCK_API=true VITE_USE_LOCAL_API=false make dev
```

For local HTTP integration, start these in three separate terminals:

```bash
make mock-neeto
make backend
VITE_USE_MOCK_API=false VITE_USE_LOCAL_API=true VITE_API_BASE_URL=http://127.0.0.1:8000 make dev
```

The mock source uses port 8001 and the local API uses 8000. Local/demo login is a
development convenience, not production authorization. Local repositories are
in memory; downloaded local documents live in `.build/local-documents`. Browser
demo data and local adapters do not fully reproduce production features or AWS
persistence. Never enable local/mock flags in a production deployment.

## Verification for changes

Use focused tests while iterating, then run checks appropriate to the final scope:

```bash
.venv/bin/python -m pytest -c backend/pytest.ini backend/tests -q
(cd frontend && npm test)
(cd frontend && npm run build)
```

- UI changes: run frontend tests and build; inspect the affected flow in a browser
  when available, including loading, empty, error, and permission states.
- Backend changes: run backend tests. Add meaningful regressions for changed
  behavior, especially authorization, data preservation, and concurrency.
- API changes: update frontend types/clients, backend validation, local/mock
  behavior, tests, and Terraform routes/permissions as needed.
- Sync/file changes: consider the local smoke test below in addition to focused
  tests. It manages its own servers; ports 8000 and 8001 must be free.
- Terraform changes: run `terraform -chdir=infrastructure/terraform fmt -check`
  and, with providers initialized, `terraform -chdir=infrastructure/terraform validate`.
  Inspect a plan against the intended state before applying infrastructure changes.
- Documentation-only changes: check commands, links, and consistency with code;
  application tests are unnecessary unless runtime behavior also changed.

```bash
.venv/bin/python scripts/local-smoke.py
git diff --check
```

Backend tests use Moto and do not require real AWS credentials. There is no
dedicated frontend lint script; `npm run build` performs TypeScript checking.
Do not claim a check passed unless it ran successfully. Explain unavailable
checks and distinguish local validation from production verification.

## Configuration and deployment

- Use `.env.example`, `frontend/.env.example`, backend settings, and Terraform
  variables to understand configuration. Avoid reading or printing real secrets.
- Keep credentials, member data, `.env` files, Terraform state/plans/private
  tfvars, and generated output out of commits. All `VITE_` values are public.
- Do not manually edit `.build/`, `frontend/dist/`, `node_modules/`, `.venv/`, or
  `.terraform/`. Keep lockfile updates intentional and related to dependency work.
- The documented JSO target uses AWS profile `jso`, region `us-east-1`, account
  `223885744552`, Terraform workspace `jso`, and private `jso.tfvars`. Verify the
  actual identity/workspace and use the existing state before deployment; these
  recorded values are not proof of the currently selected environment.
- Follow [README deployment instructions](README.md#deploy-to-jso) and
  [JSO deployment notes](docs/jso-deployment.md). The generic `make deploy` target
  does not select `jso.tfvars`. Do not assume example configuration identifies the
  existing production stack.
- A code update/refactor request alone does not request a production deployment,
  live data import, user-access change, or infrastructure destruction. Carry out
  deployment when authorized; use the requested scope and review the actual plan.

## Feature references

| Task | Read first |
| --- | --- |
| Overview, setup, deployment | [README](README.md), [local development](docs/local-development.md), [JSO deployment](docs/jso-deployment.md) |
| Profile ingestion, workers, document identity | [Architecture](docs/architecture.md), [NeetoForm setup](docs/neetform-setup.md) |
| Authentication and access | [Google authentication](docs/google-auth-setup.md), [security](docs/security.md) |
| Members and synchronization | [Member sync](docs/member-neeto-sync.md), [affiliation rules](docs/member-affiliation.md), [map](docs/member-map.md) |
| Sambhav and uploads | [Sambhav requirements](docs/sambhav-requirements.md) |
| Shared job board | [Jobs](docs/jobs.md) |
| Optional Sheets integration | [Google Sheets setup](docs/google-sheets-setup.md) |

Some older documents describe the original Profile Library or legacy deployments.
In particular, the architecture guide's no-deletion discussion concerns Idea
Incubation, not member reconciliation. Check current code, tests, and feature
guides when older documentation differs; flag unresolved requirement conflicts.

## Keep context useful for the next task

Update this file when entry points, development commands, architecture, or shared
invariants change. Update the relevant feature guide when behavior changes.
Record durable decisions and their reasons in the appropriate document, including
migration/compatibility notes when needed. Keep secrets, transient logs, and long
session transcripts out of this file.

For unfinished work, provide a short handoff with the intended outcome, changed
files, decisions, checks run, remaining work, and blockers. Do not describe planned
features as implemented. This file provides repository-wide context; separate
`SKILL.md` files are optional for reusable specialized workflows if needed later.
