import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Layout from "./components/Layout";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";
import Bookings from "./pages/Bookings";
import Retainers from "./pages/Retainers";
import Deliverables from "./pages/Deliverables";
import DeliverableDetail from "./pages/DeliverableDetail";
import Invoices from "./pages/Invoices";
import Admin from "./pages/Admin";

function Protected({ children }) {
  const { session, loading } = useAuth();
  if (loading)
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-zinc-500">Loading…</p>
      </div>
    );
  return session ? children : <Navigate to="/auth" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Toaster theme="dark" position="top-right" toastOptions={{ style: { background: "#18181b", border: "1px solid #27272a", color: "#fff" } }} />
      <BrowserRouter>
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/bookings" element={<Bookings />} />
            <Route path="/retainers" element={<Retainers />} />
            <Route path="/deliverables" element={<Deliverables />} />
            <Route path="/deliverables/:id" element={<DeliverableDetail />} />
            <Route path="/invoices" element={<Invoices />} />
            <Route path="/admin" element={<Admin />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
