# Interoperability

## The heterogeneity we deliberately simulate

| | Identity Service | Education Registry | Employment Registry |
|---|---|---|---|
| Auth | OAuth2 client credentials | Static API key header | HTTP Basic |
| Envelope | bare object | `{registry, schema_version, record}` | `{status, data}` |
| Name field | `fullName` | `student_name` (often UPPER CASE) | `candidateName` |
| Date format | `DD-MM-YYYY` | `YYYY/MM/DD` | ISO `YYYY-MM-DD` |
| Codes | gender `M/F`, `stateCode: MH` | qualification levels `SSC/HSC/B.Tech/ITI/Diploma` | `UNEMP`, `EMP`, `SALARIED` |
| Identifier | `citizenId` | `citizen_ref`, `enrollment_no` | `citizenRef`, `registrationId` |

## Canonical citizen model

```json
{
  "citizen_id": "100001",
  "full_name": "Rahul Sharma",
  "date_of_birth": "2002-03-14",
  "gender": "MALE",
  "mobile": "XXXXXX0001",
  "email": "…",
  "address": "Flat 12, Shivaji Nagar", "district": "Pune", "state": "Maharashtra", "pincode": "411005",
  "education": { "highest_qualification": "B.Tech", "qualification_level": "GRADUATE", "passing_year": 2024, "institution": "…" },
  "employment_status": "UNEMPLOYED",
  "provenance": { "full_name": {"source": "Identity Service"}, "education": {"source": "Education Registry"}, "employment_status": {"source": "Employment Registry"} }
}
```

## Pipeline

1. **Fetch** — workflow `fetch` step → consent check → connector `get_citizen()` (resilient HTTP).
2. **Transform** — connector `transform_response()` maps fields and codes using shared helpers
   (`parse_date`, `normalize_name`, `normalize_state`, `normalize_gender`, `normalize_mobile` + `mask_mobile`,
   `qualification_level`, `normalize_employment_status`). Unparseable values become warnings, not crashes.
3. **Validate** — the core validates each fragment with Pydantic (`CanonicalFragment`). Invalid fields are
   *dropped and reported* (`INVALID_FORMAT`); a payload for the wrong citizen or without mandatory structure is
   rejected (`INVALID_RESPONSE`). Connector output is never trusted blindly.
4. **Merge** — survivorship: identity attributes from the Identity Service, education from the Education
   Registry, employment from the Employment Registry, falling back in priority order; provenance is recorded per field.
5. **Quality** — checks produce issues and a per-source status (VERIFIED / WARNING / CONFLICT / NOT_FOUND /
   UNAVAILABLE): missing required fields, invalid formats, name conflicts (fuzzy, middle-name tolerant), DOB
   conflicts, stale records (> `STALE_DATA_DAYS`), duplicate citizens (same name + DOB in the golden-record store),
   invalid responses, unavailable sources.
6. **Persist** — golden record in `citizens`, snapshot on the application, findings in `data_quality_issues`.

## Demo data quality stories

| Citizen | Finding |
|---|---|
| 100001 Rahul | Education record > 1 year old → `STALE_DATA` (info) |
| 100002 Priya | "Priya Sunil Deshmukh" vs "Priya Deshmukh" → `NAME_VARIATION` (info) |
| 100003 Amit | "Amit Kumar Varma" vs "Amit Verma" → `NAME_CONFLICT`; DOB 1985-12-06 vs 1985-06-21 → `DOB_CONFLICT`; overall **CONFLICT** |
| 100004 Sneha | Identity record from 2023 → `STALE_DATA` |
| 100005 Sneha (dup) | Same name + DOB as 100004 → `DUPLICATE_RECORD` |

## Destination systems

The same SDK is used to *write* through department APIs: the Skill Development connector registers
applications (`submit_application`) and receives decisions (`update_application`, via the `department-sync`
consumer); the Grievance connector registers grievances and its status is synchronised (`get_application`).
