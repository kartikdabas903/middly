# Middly frontend

Next.js 16 portals (citizen, officer, admin) with a backend-for-frontend:
OIDC authorization code + PKCE against Keycloak, encrypted httpOnly session cookies,
and `/bff/*` proxying to the API gateway. See the repository [README](../README.md).

```bash
npm install
npm run dev            # needs the Docker stack; set FRONTEND_URL, API_BASE_URL=http://localhost:8000/api/v1,
                       # KEYCLOAK_PUBLIC_URL, OIDC_CLIENT_SECRET and SESSION_SECRET from ../.env
npx playwright test    # E2E demo against the running stack (resets demo data first)
```
