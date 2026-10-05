export type Role = "CITIZEN" | "OFFICER" | "DEPARTMENT_ADMIN" | "PLATFORM_ADMIN"

export interface SessionUser {
  sub: string
  username: string
  name: string
  email?: string
  roles: Role[]
  citizenId?: string
  department?: string
}

export const ROLE_LABELS: Record<Role, string> = {
  CITIZEN: "Citizen",
  OFFICER: "Department Officer",
  DEPARTMENT_ADMIN: "Department Admin",
  PLATFORM_ADMIN: "Platform Admin",
}

export function primaryRole(roles: Role[]): Role {
  for (const r of ["PLATFORM_ADMIN", "DEPARTMENT_ADMIN", "OFFICER", "CITIZEN"] as Role[]) {
    if (roles.includes(r)) return r
  }
  return "CITIZEN"
}

export function homeFor(roles: Role[]): string {
  const role = primaryRole(roles)
  if (role === "PLATFORM_ADMIN" || role === "DEPARTMENT_ADMIN") return "/admin/dashboard"
  if (role === "OFFICER") return "/officer/dashboard"
  return "/citizen/dashboard"
}

// Which roles may open which portal area.
export const AREA_ROLES: Record<string, Role[]> = {
  "/citizen": ["CITIZEN"],
  "/officer": ["OFFICER", "DEPARTMENT_ADMIN"],
  "/admin": ["PLATFORM_ADMIN", "DEPARTMENT_ADMIN"],
}

export function canAccess(pathname: string, roles: Role[]): boolean {
  const area = Object.keys(AREA_ROLES).find((a) => pathname === a || pathname.startsWith(a + "/"))
  if (!area) return true
  return AREA_ROLES[area].some((r) => roles.includes(r))
}
