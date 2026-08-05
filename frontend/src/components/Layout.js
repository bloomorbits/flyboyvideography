import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, Clapperboard, Repeat, Film, Receipt, ShieldCheck, LogOut, AlertTriangle } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, id: "nav-dashboard" },
  { to: "/bookings", label: "Bookings", icon: Clapperboard, id: "nav-bookings" },
  { to: "/retainers", label: "Retainers", icon: Repeat, id: "nav-retainers" },
  { to: "/deliverables", label: "Deliverables", icon: Film, id: "nav-deliverables" },
  { to: "/invoices", label: "Invoices", icon: Receipt, id: "nav-invoices" },
];

export default function Layout() {
  const { profile, session, schemaMissing, signOut } = useAuth();
  const isAdmin = profile?.role === "admin";

  return (
    <div className="relative z-10 flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-line bg-surface">
        <div className="border-b border-line px-6 py-7">
          <p className="font-display text-xl font-extrabold tracking-tighter">
            FRAME<span className="text-accent">&</span>FORM
          </p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.3em] text-zinc-500">Client Portal</p>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-6">
          {links.map(({ to, label, icon: Icon, id }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              data-testid={id}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-4 py-2.5 text-sm font-semibold ${
                  isActive ? "bg-accent/10 text-accent" : "text-zinc-400 hover:bg-raise hover:text-white"
                }`
              }
              style={{ transition: "background-color 0.15s ease, color 0.15s ease" }}
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
                `flex items-center gap-3 rounded-md px-4 py-2.5 text-sm font-semibold ${
                  isActive ? "bg-warn/10 text-warn" : "text-zinc-400 hover:bg-raise hover:text-white"
                }`
              }
            >
              <ShieldCheck size={17} strokeWidth={2.2} />
              Admin
            </NavLink>
          )}
        </nav>
        <div className="border-t border-line p-4">
          <p className="truncate text-sm font-semibold" data-testid="user-name">
            {profile?.full_name || session?.user?.email}
          </p>
          <p className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">{profile?.role || "client"}</p>
          <button
            onClick={signOut}
            data-testid="logout-btn"
            className="mt-3 flex items-center gap-2 text-xs font-bold text-zinc-500 hover:text-red-400"
            style={{ transition: "color 0.15s ease" }}
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>
      <main className="ml-60 flex-1 px-10 py-10">
        {schemaMissing && (
          <div data-testid="schema-missing-banner" className="rise mb-8 flex items-start gap-3 rounded-md border border-warn/40 bg-warn/10 p-5">
            <AlertTriangle className="mt-0.5 shrink-0 text-warn" size={18} />
            <div className="text-sm">
              <p className="font-bold text-warn">Database schema not set up yet</p>
              <p className="mt-1 text-zinc-300">
                Open your Supabase Dashboard → SQL Editor and run the contents of{" "}
                <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono text-xs text-accent">/app/supabase_schema.sql</code>, then refresh this page.
              </p>
            </div>
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
