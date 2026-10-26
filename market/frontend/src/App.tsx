import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import Countries from "./pages/Countries";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Jobs from "./pages/Jobs";
import Login from "./pages/Login";
import Mailbox from "./pages/Mailbox";
import Profile from "./pages/Profile";
import Register from "./pages/Register";
import Resumes from "./pages/Resumes";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route element={<RequireAuth />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/history" element={<History />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/countries" element={<Countries />} />
            <Route path="/resumes" element={<Resumes />} />
            <Route path="/mailbox" element={<Mailbox />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
