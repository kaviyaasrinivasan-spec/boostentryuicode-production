// src/pages/Monitoring.jsx
import { useEffect, useState } from "react";
import api from "../api/axios";
import ExcelJS from 'exceljs';
import { Download, RotateCw } from 'lucide-react';

export default function Monitoring() {
  const [docs, setDocs] = useState([]);
  const [clients, setClients] = useState([]);
  const [filterClient, setFilterClient] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterDataExtraction, setFilterDataExtraction] = useState("");
  const [filterErpEntry, setFilterErpEntry] = useState("");
  const [quickFilter, setQuickFilter] = useState("today");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  // ---------------- helpers ----------------
  const parseJsonSafe = (txt) => {
    if (!txt) return {};
    try {
      if (typeof txt === "object") return txt;
      return JSON.parse(txt);
    } catch {
      return {};
    }
  };

  const unwrapFinalData = (obj) => {
    if (obj && typeof obj === "object" && obj.final_data && typeof obj.final_data === "object") {
      return obj.final_data;
    }
    return obj && typeof obj === "object" ? obj : {};
  };

  const pickInvoiceNumber = (payloadObj) => {
    if (!payloadObj || typeof payloadObj !== "object") return "";
    const flat = {};
    for (const [k, v] of Object.entries(payloadObj)) {
      const norm = String(k).toLowerCase().replace(/[\s_-]+/g, "");
      flat[norm] = v;
    }
    const candidates = [
      "invoiceno",
      "invoicenumber",
      "invoice_no",
      "invoice_number",
      "invoicenumberno",
      "invoice",
      "invno",
      "invnumber",
    ].map((k) => k.replace(/[\s_-]+/g, ""));
    for (const key of candidates) {
      if (flat[key] != null && String(flat[key]).trim() !== "") {
        return String(flat[key]).trim();
      }
    }
    return "";
  };

  const getInvoiceText = (doc) => {
    if (doc?.invoice_no && String(doc.invoice_no).trim() !== "") return String(doc.invoice_no);
    const raw = unwrapFinalData(parseJsonSafe(doc?.extracted_json));
    const tryFromJson = pickInvoiceNumber(raw);
    if (tryFromJson) return tryFromJson;
    return "Invoice";
  };

  // ✅ Helper to get local date in YYYY-MM-DD format (avoids UTC timezone shift)
  const getLocalDateString = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  // ---------------- effects ----------------
  useEffect(() => {
    const today = getLocalDateString(new Date());
    setFromDate(today);
    setToDate(today);
    setQuickFilter("today");
    fetchClients().then(() => {
      fetchMonitoringData(today, today);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------- Manual refresh only (no auto-polling) ----------------
  // Data refreshes when: page loads, filters change, or user manually refreshes browser

  useEffect(() => {
    if (fromDate && toDate) {
      const timer = setTimeout(() => fetchMonitoringData(), 400);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterClient, filterStatus, filterDataExtraction, filterErpEntry, fromDate, toDate, quickFilter]);

  // ---------------- API calls ----------------
  const fetchClients = async () => {
    try {
      const res = await api.get("/api/clients");
      setClients(res.data?.data || []);
    } catch (err) {
      console.error("âŒ Error fetching clients:", err);
    }
  };

  const fetchMonitoringData = async (startDate = fromDate, endDate = toDate, silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterClient) params.append("client_id", filterClient);
      if (filterStatus) params.append("status", filterStatus);
      if (startDate) params.append("from_date", startDate);
      if (endDate) params.append("to_date", endDate);

      const res = await api.get(`/api/monitoring?${params.toString()}`);
      let data = res.data?.data || [];

      // Client-side filtering for Data Extraction and ERP Entry
      if (filterDataExtraction) {
        data = data.filter(doc =>
          doc.data_extraction_status &&
          doc.data_extraction_status.toLowerCase() === filterDataExtraction.toLowerCase()
        );
      }
      if (filterErpEntry) {
        data = data.filter(doc =>
          doc.erp_entry_status &&
          doc.erp_entry_status.toLowerCase() === filterErpEntry.toLowerCase()
        );
      }

      // Sort by uploaded_on in ascending order (oldest first: 1, 2, 3...)
      const sortedData = data.sort((a, b) => new Date(a.uploaded_on) - new Date(b.uploaded_on));
      if (silent) {
        // Merge/update in-place to avoid flashing UI: replace existing items and add new ones.
        setDocs((prev) => {
          const byId = new Map();
          sortedData.forEach((d) => byId.set(d.id ?? d.doc_id, d));
          // Build merged list preserving order from sortedData
          const merged = [];
          for (const d of sortedData) merged.push(d);
          return merged;
        });
      } else {
        setDocs(sortedData);
        setMessage(`✅ Loaded ${sortedData.length} document(s).`);
      }
    } catch (err) {
      console.error("❌ Error fetching monitoring data:", err);
      if (!silent) setMessage("❌ Failed to load monitoring data.");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  // ---------------- badges ----------------
  const StatusBadge = ({ status }) => {
    let colorClass = "bg-gray-100 text-gray-700";
    const s = (status || "").toString().toLowerCase();
    if (s.includes("duplicate")) {
      return (
        <span
          className="inline-block px-2 py-1 rounded text-sm font-medium border whitespace-nowrap"
          style={{ backgroundColor: "#fef9c2", color: "#92400e", borderColor: "#f7e7a8" }}
        >
          {status}
        </span>
      );
    }
    if (s.includes("success") || status === "Completed") colorClass = "bg-green-100 text-green-700";
    else if (s.includes("progress")) colorClass = "bg-yellow-100 text-yellow-700";
    else if (s.includes("failed")) colorClass = "bg-red-100 text-red-700";
    else if (s.includes("not started")) colorClass = "bg-gray-100 text-gray-600";
    else if (status === "Ready To Run") colorClass = "bg-yellow-100 text-yellow-700";

    return <span className={`inline-block px-2 py-1 rounded text-sm font-medium whitespace-nowrap ${colorClass}`}>{status}</span>;
  };

  // ðŸ‘‡ Special badge rules for ERP Entry
  const ErpBadge = ({ status }) => {
    const raw = (status || "").toString();
    const s = raw.toLowerCase().trim();

    // Exact matches first
    if (s === "duplicate") {
      return (
        <span className="px-3 py-1 rounded text-sm font-medium bg-yellow-100 text-yellow-800 border border-yellow-200">
          {raw}
        </span>
      );
    }
    if (s === "completed ahr") {
      return (
        <span
          className="px-3 py-1 rounded text-sm font-medium border"
          style={{
            backgroundColor: "#cbf7b8",
            color: "#065f46",        // dark green text
            borderColor: "#93d7a5",  // subtle border
          }}
        >
          {raw}
        </span>
      );
    }

    // Fallback to generic badge mapping
    return <StatusBadge status={raw} />;
  };

  // ---------------- utils ----------------
  const formatDateTime = (timestamp) => {
    const date = new Date(timestamp);
    if (isNaN(date)) return timestamp;
    return date.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  };

  const handleQuickFilter = (value) => {
    setQuickFilter(value);
    const today = new Date();
    let from = "";
    let to = "";

    switch (value) {
      case "today": {
        const t = getLocalDateString(today);
        from = t; to = t; break;
      }
      case "yesterday": {
        const y = new Date(today); y.setDate(today.getDate() - 1);
        const d = getLocalDateString(y);
        from = d; to = d; break;
      }
      case "last7": {
        const s7 = new Date(today); s7.setDate(today.getDate() - 7);
        from = getLocalDateString(s7);
        to = getLocalDateString(today); break;
      }
      case "thisMonth": {
        const sm = new Date(today.getFullYear(), today.getMonth(), 1);
        from = getLocalDateString(sm);
        to = getLocalDateString(today); break;
      }
      case "lastMonth": {
        const slm = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const elm = new Date(today.getFullYear(), today.getMonth(), 0);
        from = getLocalDateString(slm);
        to = getLocalDateString(elm); break;
      }
      case "last30": {
        const s30 = new Date(today); s30.setDate(today.getDate() - 30);
        from = getLocalDateString(s30);
        to = getLocalDateString(today); break;
      }
      case "last90": {
        const s90 = new Date(today); s90.setDate(today.getDate() - 90);
        from = getLocalDateString(s90);
        to = getLocalDateString(today); break;
      }
      default:
        from = ""; to = "";
    }

    setFromDate(from);
    setToDate(to);
  };

  // ---------------- Excel Download ----------------
  const handleExcelDownload = async () => {
    if (docs.length === 0) {
      alert('No data to export');
      return;
    }

    // 1. Collect all unique field names from extracted_json/corrected_json (excluding ValidationStatus)
    const allFields = new Set();
    docs.forEach(doc => {
      const extractedData = parseJsonSafe(doc.corrected_json || doc.extracted_json);
      const unwrapped = unwrapFinalData(extractedData);
      Object.keys(unwrapped).forEach(key => {
        // Exclude ValidationStatus since errors are shown in red bold text on failed fields
        if (key.toLowerCase() !== 'validationstatus' && key.toLowerCase() !== 'validation_status') {
          allFields.add(key);
        }
      });
    });
    const dynamicColumns = Array.from(allFields).sort();

    // 2. Define static columns
    const staticColumns = [
      '#', 'Client', 'Invoice', 'Uploaded On',
      'Data Extraction Status', 'Data Extraction Start', 'Data Extraction End', 'Data Extraction Time (min)',
      'Consignment Entry Status', 'Consignment Entry Start', 'Consignment Entry End', 'Consignment Entry Time (min)',
      'Vehicle Hire Status', 'Overall Status'
    ];

    // 3. Create header row
    const headers = [...staticColumns, ...dynamicColumns];

    // 4. Create ExcelJS workbook and worksheet
    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('Monitoring Data');

    // 5. Add header row
    worksheet.addRow(headers);

    // Style header row
    worksheet.getRow(1).font = { bold: true };
    worksheet.getRow(1).fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FFE0E0E0' }
    };

    // 6. Add data rows and track validation errors
    console.log('=== STARTING EXCEL EXPORT ===');
    console.log('Total documents:', docs.length);

    docs.forEach((doc, docIndex) => {
      const extractedData = parseJsonSafe(doc.corrected_json || doc.extracted_json);
      const unwrapped = unwrapFinalData(extractedData);

      // Log the first document's structure for debugging
      if (docIndex === 0) {
        console.log('First document structure:', {
          docId: doc.doc_id,
          extractedDataKeys: Object.keys(extractedData),
          unwrappedKeys: Object.keys(unwrapped),
          extractedDataSample: extractedData,
          unwrappedSample: unwrapped
        });

        // Check if validation_status exists directly in unwrapped
        console.log('Direct check - unwrapped.ValidationStatus:', unwrapped.ValidationStatus);
        console.log('Direct check - unwrapped.validation_status:', unwrapped.validation_status);
      }

      // Find validation_status with FailedFields
      const findValidation = (obj) => {
        if (!obj || typeof obj !== 'object') return null;

        for (const key of Object.keys(obj)) {
          if (key.toLowerCase() === 'validationstatus' || key.toLowerCase() === 'validation_status' || key.toLowerCase() === 'validation') {
            const val = obj[key];
            if (val && typeof val === 'object' && val.FailedFields) {
              return val;
            }
          }
        }

        for (const value of Object.values(obj)) {
          if (value && typeof value === 'object') {
            const found = findValidation(value);
            if (found) return found;
          }
        }
        return null;
      };

      const validationStatus = findValidation(unwrapped);
      const errorFieldsMap = new Map(); // Map of field name to reason

      if (validationStatus && validationStatus.FailedFields && Array.isArray(validationStatus.FailedFields)) {
        validationStatus.FailedFields.forEach(item => {
          // Handle both old format (string) and new format (object with Field and Reason)
          if (typeof item === 'string') {
            errorFieldsMap.set(item, validationStatus[item] || 'Validation failed');
          } else if (item && typeof item === 'object' && item.Field) {
            const fieldName = item.Field;
            const reason = item.Reason || 'Validation failed';

            // If field already has multiple reasons, append this one
            if (errorFieldsMap.has(fieldName)) {
              errorFieldsMap.set(fieldName, `${errorFieldsMap.get(fieldName)}; ${reason}`);
            } else {
              errorFieldsMap.set(fieldName, reason);
            }
          }
        });

        if (docIndex === 0) {
          console.log('✓ Error fields detected:', Array.from(errorFieldsMap.entries()));
        }
      }

      // Prepare static data
      const staticData = [
        docIndex + 1,
        doc.client_name || '',
        getInvoiceText(doc),
        formatDateTime(doc.uploaded_on),
        doc.data_extraction_status || '',
        doc.data_extraction_start_time || '-',
        doc.data_extraction_end_time || '-',
        doc.data_extraction_time_consumed ? `${doc.data_extraction_time_consumed}m` : '-',
        doc.erp_entry_status || '',
        doc.erp_entry_start_time || '-',
        doc.erp_entry_end_time || '-',
        doc.erp_entry_time_consumed ? `${doc.erp_entry_time_consumed}m` : '-',
        doc.vehicle_hire_status || '',
        doc.overall_status || ''
      ];

      // Prepare dynamic data with error reasons appended
      const dynamicData = dynamicColumns.map(field => {
        let value = unwrapped[field];

        // For failed fields, append error reason in brackets
        if (errorFieldsMap.has(field)) {
          const errorReason = errorFieldsMap.get(field);
          const valueStr = value === null || value === undefined ? '' :
            (typeof value === 'object' ? JSON.stringify(value) : String(value));
          return `${valueStr} (${errorReason})`;
        }

        if (value === null || value === undefined) return '';
        if (typeof value === 'object') return JSON.stringify(value);
        return String(value);
      });

      // Add row to worksheet
      const row = worksheet.addRow([...staticData, ...dynamicData]);

      // Apply red bold formatting to cells with validation errors
      dynamicColumns.forEach((field, fieldIndex) => {
        if (errorFieldsMap.has(field)) {
          const colIndex = staticColumns.length + fieldIndex + 1; // +1 because Excel is 1-indexed
          const cell = row.getCell(colIndex);
          cell.font = {
            color: { argb: 'FFFF0000' }, // Red color
            bold: true
          };
          console.log(`Applied red bold to row ${docIndex + 2}, col ${colIndex} (${field})`);
        }
      });
    });

    // 7. Set column widths
    worksheet.columns = headers.map((header, i) => {
      if (i < staticColumns.length) {
        if (header === '#') return { width: 5 };
        if (header.includes('Time')) return { width: 12 };
        if (header.includes('Status')) return { width: 18 };
        return { width: 15 };
      } else {
        return { width: 20 };
      }
    });

    // 8. Generate and download Excel file
    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `monitoring_${fromDate}_to_${toDate}.xlsx`;
    link.click();
    window.URL.revokeObjectURL(url);

    console.log('Excel file downloaded successfully');
  };

  // ---------------- Restart Service ----------------
  const handleRestartService = async () => {
    if (!window.confirm("Are you sure you want to restart the Data Entry Service? This may interrupt active tasks.")) {
      return;
    }

    try {
      // Call via Nginx proxy to avoid Mixed Content error
      // /restart-api/ proxies to http://localhost:30092/
      const response = await fetch("/restart-api/restart-data-entry", {
        method: "POST",
      });

      if (response.ok) {
        alert("✅ The data entry service has been restarted successfully.");
      } else {
        const errorData = await response.json();
        alert(`❌ Failed to restart service: ${errorData.detail || "Unknown error"}`);
      }
    } catch (error) {
      console.error("Error restarting service:", error);
      alert("❌ Error connecting to restart service. Is the service running on port 30092?");
    }
  };

  // ---------------- render ----------------
  return (
    <div className="p-6 w-full overflow-hidden">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-semibold text-indigo-700">
          Document Monitoring Dashboard
        </h2>
        <button
          onClick={handleRestartService}
          className="flex items-center gap-2 bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 transition shadow-sm"
          title="Restart Data Entry Service"
        >
          <RotateCw size={18} />
          Restart Data Entry
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6 items-end">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Quick Filter</label>
          <select
            className="border rounded px-3 py-2"
            value={quickFilter}
            onChange={(e) => handleQuickFilter(e.target.value)}
          >
            <option value="today">Today</option>
            <option value="yesterday">Yesterday</option>
            <option value="last7">Last 7 Days</option>
            <option value="thisMonth">This Month</option>
            <option value="lastMonth">Last Month</option>
            <option value="last30">Last 30 Days</option>
            <option value="last90">Last 90 Days</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">From Date</label>
          <input
            type="date"
            className="border rounded px-3 py-2"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">To Date</label>
          <input
            type="date"
            className="border rounded px-3 py-2"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Client</label>
          <select
            className="border rounded px-3 py-2"
            value={filterClient}
            onChange={(e) => setFilterClient(e.target.value)}
          >
            <option value="">All Clients</option>
            {clients.map((c) => (
              <option key={c.id ?? c.client_id} value={c.id ?? c.client_id}>
                {c.name ?? c.client_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
          <select
            className="border rounded px-3 py-2"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="">All Status</option>
            <option value="INPROGRESS">INPROGRESS</option>
            <option value="Completed">Completed</option>
            <option value="Duplicate">Duplicate</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Data Extraction</label>
          <select
            className="border rounded px-3 py-2"
            value={filterDataExtraction}
            onChange={(e) => setFilterDataExtraction(e.target.value)}
          >
            <option value="">All</option>
            <option value="Not Started">Not Started</option>
            <option value="Completed">Completed</option>
            <option value="Failed">Failed</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Consignment Entry</label>
          <select
            className="border rounded px-3 py-2"
            value={filterErpEntry}
            onChange={(e) => setFilterErpEntry(e.target.value)}
          >
            <option value="">All</option>
            <option value="Not Started">Not Started</option>
            <option value="In Progress">In Progress</option>
            <option value="Duplicate">Duplicate</option>
            <option value="Completed">Completed</option>
            <option value="Completed AHR">Completed AHR</option>
            <option value="Failed">Failed</option>
          </select>
        </div>
      </div>

      {/* Manual refresh + Download Excel button */}
      <div className="flex items-center justify-between mb-4">
        <div></div>
        <button
          onClick={handleExcelDownload}
          disabled={docs.length === 0 || loading}
          className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          <Download size={18} />
          Download Excel ({docs.length} records)
        </button>
      </div>

      {/* Loading / Message */}
      {loading ? (
        <p className="mb-4 text-sm text-indigo-600 animate-pulse">Loading data...</p>
      ) : (
        message && <p className="mb-4 text-sm text-gray-700">{message}</p>
      )}

      {/* Table Container - with explicit width constraint */}
      <div style={{ width: 'calc(100vw - 400px)', maxWidth: '100%' }}>
        <div className="overflow-x-auto overflow-y-auto max-h-[600px] bg-white shadow rounded-lg" style={{ scrollbarWidth: 'thin' }}>
          <table className="border-collapse" style={{ tableLayout: 'fixed', minWidth: '1800px' }}>
            <thead>
              <tr className="bg-indigo-50 text-gray-700 text-left text-xs">
                <th className="p-3 border-b" style={{ width: '50px' }}>#</th>
                <th className="p-3 border-b" style={{ width: '120px' }}>Client</th>
                <th className="p-3 border-b" style={{ width: '100px' }}>Invoice</th>
                <th className="p-3 border-b" style={{ width: '120px' }}>Uploaded On</th>

                {/* Data Extraction Section */}
                <th className="p-3 border-b bg-blue-50" colSpan="4" style={{ textAlign: 'center', fontWeight: 'bold' }}>Data Extraction</th>

                {/* Consignment Entry Section */}
                <th className="p-3 border-b bg-green-50" colSpan="4" style={{ textAlign: 'center', fontWeight: 'bold' }}>Consignment Entry</th>

                <th className="p-3 border-b whitespace-nowrap" style={{ width: '110px' }}>Vehicle Hire</th>
                <th className="p-3 border-b" style={{ width: '110px' }}>Overall Status</th>
              </tr>
              <tr className="bg-indigo-50 text-gray-700 text-left text-xs">
                <th className="p-2 border-b"></th>
                <th className="p-2 border-b"></th>
                <th className="p-2 border-b"></th>
                <th className="p-2 border-b"></th>

                {/* Data Extraction Subheaders */}
                <th className="p-2 border-b bg-blue-50" style={{ width: '100px' }}>Status</th>
                <th className="p-2 border-b bg-blue-50" style={{ width: '60px' }}>Start</th>
                <th className="p-2 border-b bg-blue-50" style={{ width: '60px' }}>End</th>
                <th className="p-2 border-b bg-blue-50" style={{ width: '70px' }}>Time (min)</th>

                {/* Consignment Entry Subheaders */}
                <th className="p-2 border-b bg-green-50" style={{ width: '100px' }}>Status</th>
                <th className="p-2 border-b bg-green-50" style={{ width: '60px' }}>Start</th>
                <th className="p-2 border-b bg-green-50" style={{ width: '60px' }}>End</th>
                <th className="p-2 border-b bg-green-50" style={{ width: '70px' }}>Time (min)</th>

                <th className="p-2 border-b"></th>
                <th className="p-2 border-b"></th>
              </tr>
            </thead>
            <tbody>
              {docs.length === 0 ? (
                <tr>
                  <td colSpan="14" className="text-center p-4 text-gray-500 italic">
                    No records found
                  </td>
                </tr>
              ) : (
                docs.map((doc, index) => {
                  const linkText = getInvoiceText(doc);
                  const id = doc.id || doc.doc_id;

                  return (
                    <tr key={id ?? index} className="hover:bg-gray-50 text-sm">
                      <td className="p-3 border-b">{index + 1}</td>
                      <td className="p-3 border-b">{doc.client_name}</td>

                      <td className="p-3 border-b text-indigo-600 underline cursor-pointer">
                        <a
                          href={`${window.location.origin}/invoice/${id}`}
                          onClick={(e) => {
                            e.preventDefault();
                            const width = 1300;
                            const height = 900;
                            const left = (window.screen.width - width) / 2;
                            const top = (window.screen.height - height) / 2;
                            window.open(
                              `${window.location.origin}/invoice/${id}`,
                              "_blank",
                              `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes,status=yes`
                            );
                          }}
                        >
                          {linkText}
                        </a>
                      </td>

                      <td className="p-3 border-b text-xs">{formatDateTime(doc.uploaded_on)}</td>

                      {/* Data Extraction Columns */}
                      <td className="p-2 border-b bg-blue-50">
                        <StatusBadge status={doc.data_extraction_status} />
                      </td>
                      <td className="p-2 border-b bg-blue-50 text-center text-xs">
                        {doc.data_extraction_start_time || '-'}
                      </td>
                      <td className="p-2 border-b bg-blue-50 text-center text-xs">
                        {doc.data_extraction_end_time || '-'}
                      </td>
                      <td className="p-2 border-b bg-blue-50 text-center text-xs font-semibold">
                        {doc.data_extraction_time_consumed ? `${doc.data_extraction_time_consumed}m` : '-'}
                      </td>

                      {/* Consignment Entry Columns */}
                      <td className="p-2 border-b bg-green-50">
                        <ErpBadge status={doc.erp_entry_status} />
                      </td>
                      <td className="p-2 border-b bg-green-50 text-center text-xs">
                        {doc.erp_entry_start_time || '-'}
                      </td>
                      <td className="p-2 border-b bg-green-50 text-center text-xs">
                        {doc.erp_entry_end_time || '-'}
                      </td>
                      <td className="p-2 border-b bg-green-50 text-center text-xs font-semibold">
                        {doc.erp_entry_time_consumed ? `${doc.erp_entry_time_consumed}m` : '-'}
                      </td>

                      {/* Vehicle Hire Status */}
                      <td className="p-3 border-b whitespace-nowrap">
                        <StatusBadge status={doc.vehicle_hire_status} />
                      </td>

                      <td className="p-3 border-b">
                        <StatusBadge status={doc.overall_status} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
