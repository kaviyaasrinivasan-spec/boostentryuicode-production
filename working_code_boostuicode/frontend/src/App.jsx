import { Routes, Route, Navigate } from "react-router-dom";
import DashboardLayout from "./layouts/DashboardLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import Monitoring from "./pages/Monitoring";
import VehicleHire from "./pages/VehicleHire";
import HumanReview from "./pages/HumanReview";
import FixReview from "./pages/FixReview";
import InvoiceView from "./pages/invoiceview";
import DataTransformation from "./pages/DataTransformation";

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />

      {/* Protected main routes */}
      <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/monitoring" element={<Monitoring />} />
        <Route path="/vehicle-hire" element={<VehicleHire />} />
        <Route path="/human-review" element={<HumanReview />} />
        <Route path="/data-transformation" element={<DataTransformation />} />
      </Route>

      {/* Standalone pages without protection */}
      <Route path="/human-review/fix/:id" element={<FixReview />} />
      <Route path="/invoice/:id" element={<InvoiceView />} />

      {/* Fallback for unknown routes */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
