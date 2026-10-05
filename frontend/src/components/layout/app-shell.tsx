"use client"

import { useQuery } from "@tanstack/react-query"
import {
  Bell,
  Cable,
  ClipboardList,
  FileSearch,
  FlaskConical,
  GitBranch,
  Inbox,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Radio,
  ShieldAlert,
  ShieldCheck,
  UserRound,
  type LucideIcon,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"

import { Brand } from "@/components/layout/brand"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { api } from "@/lib/api"
import { ROLE_LABELS, primaryRole, type SessionUser } from "@/lib/roles"
import { cn } from "@/lib/utils"

type Area = "citizen" | "officer" | "admin"
interface NavItem {
  href: string
  label: string
  icon: LucideIcon
}
interface NavGroup {
  title?: string
  items: NavItem[]
}

function navFor(area: Area, user: SessionUser, sandbox: boolean): NavGroup[] {
  if (area === "citizen") {
    return [
      { items: [{ href: "/citizen/dashboard", label: "Overview", icon: LayoutDashboard }] },
      {
        title: "Applications",
        items: [
          { href: "/citizen/applications", label: "My applications", icon: ClipboardList },
          { href: "/citizen/apply", label: "Apply for a service", icon: Plus },
        ],
      },
      {
        title: "Account",
        items: [
          { href: "/citizen/notifications", label: "Notifications", icon: Bell },
          { href: "/citizen/consents", label: "Consents", icon: ShieldCheck },
          { href: "/citizen/profile", label: "My records", icon: UserRound },
        ],
      },
    ]
  }
  if (area === "officer") {
    const groups: NavGroup[] = [
      {
        items: [
          { href: "/officer/dashboard", label: "Overview", icon: LayoutDashboard },
          { href: "/officer/applications", label: "Review queue", icon: Inbox },
        ],
      },
    ]
    if (user.roles.includes("DEPARTMENT_ADMIN")) groups.push({ title: "Administration", items: [{ href: "/admin/dashboard", label: "Platform", icon: LayoutDashboard }] })
    return groups
  }
  const groups: NavGroup[] = [
    { items: [{ href: "/admin/dashboard", label: "Overview", icon: LayoutDashboard }] },
    {
      title: "Integration",
      items: [
        { href: "/admin/connectors", label: "Connectors", icon: Cable },
        { href: "/admin/workflows", label: "Workflows", icon: GitBranch },
        { href: "/admin/events", label: "Events", icon: Radio },
      ],
    },
    {
      title: "Governance",
      items: [
        { href: "/admin/data-quality", label: "Data quality", icon: ShieldAlert },
        { href: "/admin/audit-logs", label: "Audit log", icon: FileSearch },
      ],
    },
  ]
  if (user.roles.includes("OFFICER")) groups.push({ title: "Department", items: [{ href: "/officer/applications", label: "Review queue", icon: Inbox }] })
  if (sandbox && user.roles.includes("PLATFORM_ADMIN")) groups.push({ title: "Environment", items: [{ href: "/admin/sandbox", label: "Sandbox tools", icon: FlaskConical }] })
  return groups
}

function initials(name: string) {
  return name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

function Sidebar({ area, user, sandbox, onNavigate }: { area: Area; user: SessionUser; sandbox: boolean; onNavigate?: () => void }) {
  const pathname = usePathname()
  const groups = navFor(area, user, sandbox)
  return (
    <div className="flex h-full flex-col bg-sidebar">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <Brand href={`/${area}/dashboard`} />
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4" aria-label="Primary">
        {groups.map((g, i) => (
          <div key={g.title ?? i}>
            {g.title && <p className="mb-1 px-2.5 text-[11px] font-medium tracking-wide text-muted-foreground/80 uppercase">{g.title}</p>}
            <ul className="space-y-0.5">
              {g.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/")
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                        active ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <item.icon className={cn("size-4", active ? "text-primary" : "text-muted-foreground")} aria-hidden />
                      {item.label}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t p-3">
        <div className="flex items-center gap-2.5 rounded-md px-1.5 py-1">
          <Avatar className="size-8">
            <AvatarFallback className="bg-accent text-xs font-semibold text-accent-foreground">{initials(user.name)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-sm font-medium">{user.name}</p>
            <p className="truncate text-xs text-muted-foreground">{ROLE_LABELS[primaryRole(user.roles)]}</p>
          </div>
          <a href="/auth/logout" className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="Sign out" title="Sign out">
            <LogOut className="size-4" />
          </a>
        </div>
      </div>
    </div>
  )
}

function NotificationBell() {
  const { data } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api.get<{ unread: number }>("notifications/unread-count"),
    refetchInterval: 5000,
  })
  const unread = data?.unread ?? 0
  return (
    <Link
      href="/citizen/notifications"
      className="relative inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
      aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`}
      data-testid="notification-bell"
    >
      <Bell className="size-[18px]" />
      {unread > 0 && (
        <span className="absolute top-1 right-1 flex min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] leading-4 font-semibold text-white">
          {unread > 9 ? "9+" : unread}
        </span>
      )}
    </Link>
  )
}

const SUBTITLE: Record<Area, (u: SessionUser) => string> = {
  citizen: (u) => (u.citizenId ? `Citizen ID ${u.citizenId}` : "Citizen"),
  officer: (u) => (u.department ? `Department · ${u.department.replaceAll("_", " ").toLowerCase()}` : "Department"),
  admin: () => "Platform administration",
}

export function AppShell({
  area,
  user,
  sandbox = false,
  children,
}: {
  area: Area
  user: SessionUser
  sandbox?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  const role = primaryRole(user.roles)

  return (
    <div className="flex min-h-screen flex-1">
      <aside className="hidden w-60 shrink-0 border-r bg-sidebar lg:block">
        <div className="sticky top-0 h-screen">
          <Sidebar area={area} user={user} sandbox={sandbox} />
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-md sm:px-6">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger render={<Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation" />}>
              <Menu className="size-5" />
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <Sidebar area={area} user={user} sandbox={sandbox} onNavigate={() => setOpen(false)} />
            </SheetContent>
          </Sheet>
          <p className="truncate text-sm text-muted-foreground capitalize">{SUBTITLE[area](user)}</p>
          <div className="ml-auto flex items-center gap-1">
            {area === "citizen" && <NotificationBell />}
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="ghost" className="h-9 gap-2 px-1.5" data-testid="user-menu" />}>
                <Avatar className="size-7">
                  <AvatarFallback className="bg-accent text-[11px] font-semibold text-accent-foreground">{initials(user.name)}</AvatarFallback>
                </Avatar>
                <span className="hidden text-sm font-medium sm:block">{user.name.split(" ")[0]}</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuGroup>
                  <DropdownMenuLabel>
                    <span className="block font-medium text-foreground">{user.name}</span>
                    <span className="block text-xs font-normal">
                      @{user.username} · {ROLE_LABELS[role]}
                    </span>
                  </DropdownMenuLabel>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                <DropdownMenuItem render={<a href="/auth/logout" />} data-testid="logout">
                  <LogOut className="size-4" /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main id="main" className="flex-1 px-4 py-8 sm:px-6 lg:px-10">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  )
}
