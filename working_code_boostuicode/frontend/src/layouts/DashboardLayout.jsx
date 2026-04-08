import { useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { LogOut, LayoutDashboard, Upload, Monitor, ClipboardCheck, Menu, ArrowLeftRight, Truck } from "lucide-react";

export default function DashboardLayout() {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem("isLoggedIn");
    navigate("/login");
  };

  return (
    <div className="flex min-h-screen bg-gray-50 overflow-x-hidden">
      {/* MOBILE SIDEBAR (overlay) */}
      <div className={`fixed inset-0 z-40 md:hidden transition-opacity ${sidebarOpen ? "block" : "pointer-events-none"}`}>
        <div
          className={`absolute inset-0 bg-black/40 transition-opacity ${sidebarOpen ? "opacity-100" : "opacity-0"}`}
          onClick={() => setSidebarOpen(false)}
        />
        <aside className={`absolute left-0 top-0 bottom-0 w-72 bg-[#3B29D9] text-white p-4 transform transition-transform ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
          <div className="text-center py-3 border-b border-indigo-500/25">
            <h1 className="text-lg font-semibold tracking-wide">BoosterEntryAI</h1>
          </div>

          <nav className="mt-4 space-y-1">
            <NavLink to="/dashboard" onClick={() => setSidebarOpen(false)} className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
              <LayoutDashboard size={18} /> Dashboard
            </NavLink>

            <NavLink to="/upload" onClick={() => setSidebarOpen(false)} className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
              <Upload size={18} /> Upload
            </NavLink>

            <NavLink to="/monitoring" onClick={() => setSidebarOpen(false)} className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
              <Monitor size={18} /> Monitoring
            </NavLink>

            <NavLink to="/vehicle-hire" onClick={() => setSidebarOpen(false)} className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
              <Truck size={18} /> Vehicle Hire
            </NavLink>

            <NavLink to="/human-review" onClick={() => setSidebarOpen(false)} className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
              <ClipboardCheck size={18} /> Human Review
            </NavLink>

            <NavLink to="/data-transformation" onClick={() => setSidebarOpen(false)} className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
              <ArrowLeftRight size={18} /> Data Transformation
            </NavLink>
          </nav>
        </aside>
      </div>

      {/* DESKTOP SIDEBAR */}
      <aside className="hidden md:flex w-64 flex-shrink-0 bg-[#3B29D9] text-white flex-col">
        <div className="text-center py-4 border-b border-indigo-500/25 shadow-sm">
          <h1 className="text-[20px] font-semibold text-white tracking-wide">BoosterEntryAI</h1>
        </div>

        <nav className="flex flex-col space-y-1 px-3 mt-3">
          <NavLink to="/dashboard" className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] transition ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
            <LayoutDashboard size={18} /> Dashboard
          </NavLink>

          <NavLink to="/upload" className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] transition ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
            <Upload size={18} /> Upload
          </NavLink>

          <NavLink to="/monitoring" className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] transition ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
            <Monitor size={18} /> Monitoring
          </NavLink>

          <NavLink to="/vehicle-hire" className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] transition ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
            <Truck size={18} /> Vehicle Hire
          </NavLink>

          <NavLink to="/human-review" className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] transition ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
            <ClipboardCheck size={18} /> Human Review
          </NavLink>

          <NavLink to="/data-transformation" className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-lg text-[15px] transition ${isActive ? "bg-[#5243F3] text-white font-semibold" : "text-indigo-100 hover:bg-[#5243F3] hover:text-white"}`}>
            <ArrowLeftRight size={18} /> Data Transformation
          </NavLink>
        </nav>
      </aside>

      {/* MAIN */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-white shadow-sm flex items-center justify-between px-4 md:px-8 py-3">
          <div className="flex items-center gap-3">
            {/* Mobile hamburger */}
            <button onClick={() => setSidebarOpen(true)} className="md:hidden p-2 rounded hover:bg-gray-100" aria-label="Open menu">
              <Menu size={20} />
            </button>
            <h2 className="text-[18px] font-medium text-gray-800 tracking-wide hidden sm:block">KSS Roadways</h2>
          </div>

          <div className="flex items-center gap-4">
            <button onClick={handleLogout} className="flex items-center gap-2 text-gray-500 hover:text-gray-700 transition px-3 py-1 rounded">
              <LogOut size={18} strokeWidth={1.5} />
              <span className="text-[15px] font-medium hidden sm:inline">Logout</span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 md:p-6 overflow-y-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
