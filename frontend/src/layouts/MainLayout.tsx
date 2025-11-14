import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { Outlet } from "react-router-dom";

export default function MainLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-900 text-white">
      <Navbar />

      <div className="pt-20 pb-20 flex-1">
        <Outlet />
      </div>

      <Footer />
    </div>
  );
}
