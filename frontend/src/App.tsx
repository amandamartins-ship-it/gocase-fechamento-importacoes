import { useState } from "react";
import { getToken } from "./api/client";
import Login from "./pages/Login";
import Home from "./pages/Home";

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean>(!!getToken());

  if (!authenticated) {
    return <Login onLogin={() => setAuthenticated(true)} />;
  }
  return <Home onLogout={() => setAuthenticated(false)} />;
}
