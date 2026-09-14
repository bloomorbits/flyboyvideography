import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, Clapperboard, Repeat, Film, Receipt, ShieldCheck, ShieldAlert, LogOut, AlertTriangle, UserRound, Menu, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, id: "nav-dashboard" },
  { to: "/bookings", label: "Bookings", icon: Clapperboard, id: "nav-bookings" },
  { to: "/retainers", label: "Retainers", icon: Repeat, id: "nav-retainers" },
  { to: "/deliverables", label: "Deliverables", icon: Film, id: "nav-deliverables" },
  { to: "/invoices", label: "Invoices", icon: Receipt, id: "nav-invoices" },
  { to: "/profile", label: "Profile", icon: UserRound, id: "nav-profile" },
];

const navLinkClass = ({ isActive }) =>
  `flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
    isActive ? "bg-ink text-cream" : "text-ink/70 hover:bg-sand hover:text-ink"
  }`;

export default function Layout() {
  const { profile, session, schemaMissing, signOut } = useAuth();
  const isAdmin = profile?.role === "admin";
  const [navOpen, setNavOpen] = useState(false);
  const close = () => setNavOpen(false);

  return (
    <div className="relative z-10 flex min-h-screen">
      {/* Mobile top bar — only below md. Carries the brand + hamburger. */}
      <header className="fixed inset-x-0 top-0 z-30 flex items-center justify-between border-b border-dune bg-cream px-4 py-3 md:hidden">
        <p className="font-display text-lg font-bold tracking-tight text-ink">
          FLYBOY<span className="text-accent">/</span>VIDEO
        </p>
        <button
          onClick={() => setNavOpen(true)}
          data-testid="mobile-nav-open"
          aria-label="Open navigation menu"
          className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-dune text-ink transition-colors hover:bg-sand"
        >
          <Menu size={20} strokeWidth={2.2} />
        </button>
      </header>

      {/* Backdrop when the mobile drawer is open. */}
      {navOpen && (
        <div
          onClick={close}
          data-testid="mobile-nav-backdrop"
          aria-hidden
          className="fixed inset-0 z-30 bg-ink/40 backdrop-blur-sm md:hidden"
        />
      )}

      <aside
        data-testid="portal-sidebar"
        data-open={navOpen}
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-dune bg-cream transition-transform duration-300 ease-out md:z-20 md:translate-x-0 ${
          navOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-start justify-between border-b border-dune px-6 py-7">
          <div>
            <p className="font-display text-xl font-bold tracking-tight text-ink">
              FLYBOY<span className="text-accent">/</span>VIDEO
            </p>
            <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.3em] text-ink/70">Client Portal</p>
          </div>
          <button
            onClick={close}
            data-testid="mobile-nav-close"
            aria-label="Close navigation menu"
            className="-mr-1 inline-flex h-9 w-9 items-center justify-center rounded-lg text-ink/60 transition-colors hover:bg-sand hover:text-ink md:hidden"
          >
            <X size={18} strokeWidth={2.2} />
          </button>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-6">
          {links.map(({ to, label, icon: Icon, id }) => (
            <NavLink key={to} to={to} end={to === "/"} data-testid={id} onClick={close} className={navLinkClass}>
              <Icon size={17} strokeWidth={2.2} />
              {label}
            </NavLink>
          ))}
          {isAdmin && (
            <NavLink to="/admin" data-testid="nav-admin" onClick={close} className={navLinkClass}>
              <ShieldCheck size={17} strokeWidth={2.2} />
              Admin
            </NavLink>
          )}
          {isAdmin && (
            <NavLink to="/admin/security" data-testid="nav-admin-security" onClick={close} className={navLinkClass}>
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

      <main className="flex-1 px-4 pb-10 pt-20 md:ml-60 md:px-10 md:py-10">
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
