import { Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Explorer from "./pages/Explorer";
import Dashboard from "./pages/Dashboard";
import Workspace from "./pages/Workspace";
import Schemes from "./pages/Schemes";
import About from "./pages/About";

export default function App() {
  const location = useLocation();

  return (
    <Layout>
      <div key={location.pathname} className="page-enter">
        <Routes location={location}>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/schemes" element={<Schemes />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </div>
    </Layout>
  );
}
