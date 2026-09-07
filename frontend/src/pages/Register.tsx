import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuthStore } from "../store/auth";
import logo from "../assets/logo.png";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const field =
  "w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft";

export default function Register() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((s) => s.setTokens);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { data } = await axios.post(`${baseURL}/api/auth/register`, { name, email, password });
      setTokens(data.access_token, data.refresh_token);
      navigate("/");
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? err.response?.data?.error?.message ?? "Registration failed"
          : "Registration failed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ground p-6">
      <div className="w-[380px]">
        <div className="mb-7 flex items-center justify-center gap-2.5">
          <img src={logo} alt="" className="h-8 w-8" />
          <span className="text-xl font-bold tracking-tight">Paper&nbsp;Trading</span>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-7 shadow-sm">
          <h1 className="text-[19px] font-semibold">Create account</h1>
          <p className="mb-5 mt-1 text-[13px] text-muted">Starts with ₹10,00,000 in virtual funds.</p>
          <form onSubmit={submit} className="space-y-3.5">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-muted">Name</span>
              <input className={field} value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-muted">Email</span>
              <input
                className={field}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-muted">Password</span>
              <input
                className={field}
                type="password"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
            </label>
            {error && <p className="text-sm text-down">{error}</p>}
            <button className="btn-primary w-full py-2.5" disabled={busy}>
              {busy ? "…" : "Create account"}
            </button>
          </form>
        </div>
        <p className="mt-4 text-center text-[13px] text-muted">
          Have an account?{" "}
          <Link to="/login" className="font-medium text-accent hover:text-accent-hover">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
