# Connectors

Each folder is one department integration:

```
connectors/<department>/
  connector.py        # plugin implementing BaseConnector (loaded by the platform at runtime)
  mock_service/       # DEMO / MOCK department system (FastAPI) with fictitious data
```

`mock_common/` holds the shared mock scaffolding (fault injection, demo reset, auth schemes).
`Dockerfile.mock` builds any mock: `--build-arg SERVICE_DIR=<department>`.

| Folder | Connector key | Auth | Format quirks |
|---|---|---|---|
| identity | `identity` | OAuth2 client credentials | camelCase, `DD-MM-YYYY`, gender/state codes, free-form phone |
| education | `education` | API key (`X-API-Key`) | snake_case envelope, `YYYY/MM/DD`, list of qualifications |
| employment | `employment` | HTTP Basic | `{status,data}` envelope, legacy codes `UNEMP`/`EMP`/`SALARIED` |
| skill-development | `skill` | API key (`X-Dept-Key`) | destination system, PascalCase statuses |
| grievance | `grievance` | OAuth2 client credentials | ticket model, status progresses inside the department |

## Adding a department (e.g. Agriculture)

1. Create `connectors/agriculture/connector.py`:

```python
from app.integration.sdk import BaseConnector, SourceRecord
from app.integration.normalize import normalize_name, parse_date

class AgricultureConnector(BaseConnector):
    key = "agriculture"
    name = "Agriculture Registry Connector"
    system_name = "Agriculture Registry"
    department_code = "AGRICULTURE_DEPT"
    data_categories = ["LAND_RECORDS"]
    auth_type = "API_KEY"
    capabilities = ["health_check", "get_citizen"]
    default_base_url = "http://mock-agriculture:8000"
    base_url_env = "AGRICULTURE_BASE_URL"
    credential_env = {"api_key": "AGRICULTURE_API_KEY"}

    def authenticate(self):
        return {"X-API-Key": self.config.credentials["api_key"]}

    def get_citizen(self, citizen_id):
        return self.transform_response(self.get_json(f"/farmers/{citizen_id}"), citizen_id=citizen_id)

    def transform_response(self, raw, kind="citizen", **ctx):
        return SourceRecord(self.key, "LAND_RECORDS", ctx["citizen_id"], {"citizen_id": ctx["citizen_id"], "full_name": normalize_name(raw["farmer_name"])})
```

2. Restart the backend/worker. The registry discovers the plugin and registers it in the
   `connectors` table; it appears on the admin Connectors page with live health checks.
3. Reference it from a workflow definition (`{"type": "fetch", "connector": "agriculture", "category": "LAND_RECORDS"}`).

Timeouts, retries with exponential backoff, the circuit breaker, telemetry (`connector_calls`,
Prometheus metrics), consent checks and audit logging are provided by the SDK and core — the
plugin only describes *how to talk to the department and how to map its data*.
