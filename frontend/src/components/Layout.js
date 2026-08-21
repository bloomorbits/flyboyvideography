import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, Clapperboard, Repeat, Film, Receipt, ShieldCheck, ShieldAlert, LogOut, AlertTriangle, UserRound } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, id: "nav-dashboard" },
  { to: "/bookings", label: "Bookings", icon: Clapperboard, id: "nav-bookings" },
  { to: "/retainers", label: "Retainers", icon: Repeat, id: "nav-retainers" },
  { to: "/deliverables", label: "Deliverables", icon: Film, id: "nav-deliverables" },
  { to: "/invoices", label: "Invoices", icon: Receipt, id: "nav-invoices" },
  { to: "/profile", label: "Profile", icon: UserRound, id: "nav-profile" },
];

export default function Layout() {
  const { profile, session, schemaMissing, signOut } = useAuth();
  const isAdmin = profile?.role === "admin";

  return (
    <div className="relative z-10 flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-dune bg-cream">
        <div className="border-b border-dune px-6 py-7">
          <p className="font-display text-xl font-bold tracking-tight text-ink">
            FLYBOY<span className="text-accent">/</span>VIDEO
          </p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.3em] text-ink/70">Client Portal</p>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-6">
          {links.map(({ to, label, icon: Icon, id }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              data-testid={id}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-ink text-cream" : "text-ink/70 hover:bg-sand hover:text-ink"
                }`
              }
            >
              <Icon size={17} strokeWidth={2.2} />
              {label}
            </NavLink>
          ))}
          {isAdmin && (
            <NavLink
              to="/admin"
              data-testid="nav-admin"
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-ink text-cream" : "text-ink/70 hover:bg-sand hover:text-ink"
                }`
              }
            >
              <ShieldCheck size={17} strokeWidth={2.2} />
              Admin
            </NavLink>
          )}
          {isAdmin && (
            <NavLink
              to="/admin/security"
              data-testid="nav-admin-security"
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-ink text-cream" : "text-ink/70 hover:bg-sand hover:text-ink"
                }`
              }
            >
              <ShieldAlert size={17} strokeWidth={2.2} />
              Security
            </NavLink>
          )}
        </nav>
        <div className="border-t border-dune p-4">
          <p className="truncate text-sm font-medium text-ink" data-testid="user-name">
            {profile?.full_name || session?.user?.email}
          </p>
          <p className="font-mono text-[10px] uppercase tracking-widest text-ink/70">{profile?.role || "client"}</p>
          <button
            onClick={signOut}
            data-testid="logout-btn"
            className="mt-3 flex items-center gap-2 text-xs font-medium text-ink/60 transition-colors hover:text-red-600"
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>
      <main className="ml-60 flex-1 px-10 py-10">
        {schemaMissing && (
          <div data-testid="schema-missing-banner" className="rise mb-8 flex items-start gap-3 rounded-lg border border-[#B45309]/30 bg-[#B45309]/5 p-5">
            <AlertTriangle className="mt-0.5 shrink-0 text-[#B45309]" size={18} />
            <div className="text-sm">
              <p className="font-semibold text-[#B45309]">Database schema not set up yet</p>
              <p className="mt-1 text-ink/70">
                Open your Supabase Dashboard → SQL Editor and run the contents of{" "}
                <code className="rounded bg-sand px-1.5 py-0.5 font-mono text-xs text-ink">/app/supabase_schema.sql</code>, then refresh this page.
              </p>
            </div>
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
