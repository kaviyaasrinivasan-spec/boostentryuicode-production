// src/components/ProtectedRoute.jsx
import React from "react";
import { Navigate, useLocation, Outlet } from "react-router-dom";

function isAuthenticated() {
  // strict check
  return localStorage.getItem("isLoggedIn") === "true";
}

export default function ProtectedRoute({ children }) {
  const location = useLocation();

  if (!isAuthenticated()) {
    // keep where the user tried to go, so Login can redirect back
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // Works for both usages:
  // 1) <ProtectedRoute><DashboardLayout/></ProtectedRoute>
  // 2) <Route element={<ProtectedRoute/>}><Route path="..." element={<Page/>} /></Route>
  return children ?? <Outlet />;
}
