import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createBrowserRouter, Navigate } from "react-router-dom";
import "./index.css";
import { useAuthStore } from "./store/auth";
import { applyTheme, useTheme } from "./store/theme";
import Login from "./pages/Login";
import Settings from "./pages/Settings";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Chart from "./pages/Chart";
import Orders from "./pages/Orders";
import Positions from "./pages/Positions";
import Holdings from "./pages/Holdings";
import OptionChain from "./pages/OptionChain";
import Reports from "./pages/Reports";
import Leaderboard from "./pages/Leaderboard";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";

// theme: apply before first paint, then keep in sync with the store + OS setting
applyTheme(useTheme.getState());
useTheme.subscribe((s) => applyTheme(s));
window.matchMedia?.("(prefers-color-scheme: dark)")
  .addEventListener?.("change", () => applyTheme(useTheme.getState()));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.accessToken);
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  { path: "/register", element: <Register /> },
  {
    path: "/",
    element: (
      <RequireAuth>
        <Layout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Dashboard /> },
      { path: "chart", element: <Chart /> },
      { path: "orders", element: <Orders /> },
      { path: "positions", element: <Positions /> },
      { path: "holdings", element: <Holdings /> },
      { path: "options", element: <OptionChain /> },
      { path: "reports", element: <Reports /> },
      { path: "leaderboard", element: <Leaderboard /> },
      { path: "settings", element: <Settings /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
