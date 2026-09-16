# Local development

Install Node 22.12+, Python 3.12+, and npm. From the repository root:

```bash
make setup
make dev
```

The copied `frontend/.env.local` enables an entirely browser-local mock. Login accepts any nonempty credentials; it is not production authentication. The mock includes fictional examples and a harmless PDF. Changes are in memory and reset on restart/reload.

For real HTTP integration without AWS:

```bash
# Terminal 1
make mock-neeto
# Terminal 2
make backend
# Terminal 3
VITE_USE_MOCK_API=false VITE_USE_LOCAL_API=true make dev
```

The mock Neeto server listens on 127.0.0.1:8001, serves the documented paginated API shape and sample PDFs. The local backend listens on 127.0.0.1:8000, uses memory repositories, and accepts `Bearer local-dev-token`. The explicit local frontend flag uses this token. These flags are forbidden in production builds by deployment configuration. Local HTTP file downloads are permitted only for loopback addresses.

```bash
make test
.venv/bin/python scripts/local-smoke.py
./scripts/test-webhook.sh
./scripts/test-invalid-webhook.sh
```

The smoke script starts and stops its own local servers, synchronizes samples, checks duplicate delivery and signature rejection. Leave ports 8000/8001 free. The manual webhook scripts assume the backend is already running. `NEETO_WEBHOOK_SECRET` defaults to the local demonstration value when using local tools; set it consistently for your own fixtures.

Use ignored `.env` for backend-only local settings and `frontend/.env.local` for public frontend settings. Never use production secrets in UI mock fixtures. Python tests use Moto for AWS behavior and do not need AWS credentials. Lambda packages are built for Python 3.12 using pure Python wheels; run local tests on Python 3.12+ for parity.
