import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import { useMe } from "../api/hooks";
import WatchlistRail from "./WatchlistRail";
import OrderPad from "./OrderPad";
import logo from "../assets/logo.png";

const links: [string, string][] = [
  ["/", "Dashboard"],
  ["/chart", "Chart"],
  ["/orders", "Orders"],
  ["/positions", "Positions"],
  ["/holdings", "Holdings"],
  ["/options", "Options"],
  ["/reports", "Reports"],
  ["/leaderboard", "Leaderboard"],
];

const linkCls = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-2.5 py-1.5 text-[13px] ${
    isActive
      ? "bg-accent-soft font-semibold text-accent"
      : "font-medium text-muted hover:bg-surface-2"
  }`;

export default function Layout() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const { data: me } = useMe();

  return (
    <div className="min-h-screen">
      <header className="flex h-14 items-center justify-between border-b border-line bg-surface px-6">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <img src={logo} alt="" className="h-6 w-6" />
            <span className="text-[15px] font-bold tracking-tight">Paper&nbsp;Trading</span>
          </div>
          <nav className="hidden flex-wrap gap-0.5 md:flex">
            {links.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"} className={linkCls}>
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2 text-sm">
          {me && <span className="mr-1 text-muted">{me.name}</span>}
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `grid h-8 w-8 place-items-center rounded-lg ${
                isActive ? "bg-accent-soft text-accent" : "text-muted hover:bg-surface-2"
              }`
            }
            title="Settings"
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.36.63.97 1.05 1.51 1.05H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </NavLink>
          <button className="btn-ghost" onClick={() => { logout(); navigate("/login"); }}>
            Log out
          </button>
        </div>
      </header>

      <div className="flex items-stretch">
        <div className="hidden lg:block">
          <WatchlistRail />
        </div>
        <main className="min-w-0 flex-1 bg-ground p-7">
          <div className="mx-auto max-w-[1120px]">
            <Outlet />
          </div>
        </main>
      </div>

      <OrderPad />
    </div>
  );
}
