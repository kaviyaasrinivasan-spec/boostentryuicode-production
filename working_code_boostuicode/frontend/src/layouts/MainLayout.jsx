import { Outlet } from "react-router-dom";
import Dashboard from "../pages/Dashboard";

export default function MainLayout() {
  return (
    <Dashboard>
      <Outlet />
    </Dashboard>
  );
}
