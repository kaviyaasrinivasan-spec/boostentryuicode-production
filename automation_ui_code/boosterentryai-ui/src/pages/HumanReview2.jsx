import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

export default function HumanReview() {
  const [docs, setDocs] = useState([]);
  const [clients, setClients] = useState([]);
  const [filterClient, setFilterClient] = useState("");
  const [filterDataExtraction, setFilterDataExtraction] = useState("");
  const [filterErpEntry, setFilterErpEntry] = useState("Failed");
  const [quickFilter, setQuickFilter] = useState("today");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  // ---------------- helpers (invoice extraction like Monitoring) ----------------
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

  // ✅ Load data
  useEffect(() => {
    const today = new Date().toISOString().split("T")[0];
    setFromDate(today);
    setToDate(today);
    fetchClients().then(() => fetchHumanReviewData(today, today));
  }, []);

  useEffect(() => {
    if (fromDate && toDate) {
      const timer = setTimeout(() => fetchHumanReviewData(), 400);
      return () => clearTimeout(timer);
    }
  }, [filterClient, filterDataExtraction, filterErpEntry, fromDate, toDate, quickFilter]);

  const fetchClients = async () => {
    try {
      const res = await api.get("/api/clients");
      setClients(res.data.data);
    } catch (err) {
      console.error("❌ Error fetching clients:", err);
    }
  };

  const fetchHumanReviewData = async (start = fromDate, end = toDate) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterClient) params.append("client_id", filterClient);
      if (start) params.append("from_date", start);
      if (end) params.append("to_date", end);

      const res = await api.get(`/api/human_review?${params.toString()}`);
      let data = res.data.data || [];
      
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
      setDocs(sortedData);
      setMessage(`✅ ${sortedData.length} document(s) requiring human review.`);
    } catch (err) {
      console.error("❌ Error fetching data:", err);
      setMessage("❌ Failed to load human review data.");
    } finally {
      setLoading(false);
    }
  };

  const formatDateTime = (timestamp) => {
    const date = new Date(timestamp);
    if (isNaN(date)) return timestamp;
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  };

  const StatusBadge = ({ status }) => {
    let colorClass = "bg-gray-100 text-gray-700";
    if (status?.toLowerCase().includes("success") || status === "Completed")
      colorClass = "bg-green-100 text-green-700";
    else if (status?.toLowerCase().includes("progress"))
      colorClass = "bg-yellow-100 text-yellow-700";
    else if (status?.toLowerCase().includes("failed"))
      colorClass = "bg-red-100 text-red-700";
    else if (status?.toLowerCase().includes("not started"))
      colorClass = "bg-gray-100 text-gray-600";

    return (
      <span className={`px-3 py-1 rounded text-sm font-medium ${colorClass}`}>
        {status}
      </span>
    );
  };

  // ✅ Fix button — opens full new browser window (like screenshot #1)
  const handleFix = (doc) => {
    if (!doc?.id && !doc?.doc_id) {
      console.error("❌ Invalid document data:", doc);
      return;
    }

    const docId = doc.id ?? doc.doc_id;
    const url = `${window.location.origin}/human-review/fix/${docId}`;


    // Open in full browser window (not just a popup)
    window.open(url, "_blank");
  };

  const handleQuickFilter = (value) => {
    setQuickFilter(value);
    const today = new Date();
    let from = "",
      to = "";
    switch (value) {
      case "today":
        from = to = today.toISOString().split("T")[0];
        break;
      case "last7":
        const s7 = new Date(today);
        s7.setDate(today.getDate() - 7);
        from = s7.toISOString().split("T")[0];
        to = today.toISOString().split("T")[0];
        break;
      default:
        from = "";
        to = "";
    }
    setFromDate(from);
    setToDate(to);
  };

  return (
    <div className="p-6">
      <h2 className="text-2xl font-semibold text-indigo-700 mb-6">
        Human Review Dashboard
      </h2>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6 items-end">
        <div>
          <label className="block text-sm font-medium mb-1">Quick Filter</label>
          <select
            className="border rounded px-3 py-2"
            value={quickFilter}
            onChange={(e) => handleQuickFilter(e.target.value)}
          >
            <option value="today">Today</option>
            <option value="last7">Last 7 Days</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">From Date</label>
          <input
            type="date"
            className="border rounded px-3 py-2"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">To Date</label>
          <input
            type="date"
            className="border rounded px-3 py-2"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Client</label>
          <select
            className="border rounded px-3 py-2"
            value={filterClient}
            onChange={(e) => setFilterClient(e.target.value)}
          >
            <option value="">All Clients</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Data Extraction</label>
          <select
            className="border rounded px-3 py-2"
            value={filterDataExtraction}
            onChange={(e) => setFilterDataExtraction(e.target.value)}
          >
            <option value="">All</option>
            <option value="Not Started">Not Started</option>
            <option value="Completed">Completed</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">ERP Entry</label>
          <select
            className="border rounded px-3 py-2"
            value={filterErpEntry}
            onChange={(e) => setFilterErpEntry(e.target.value)}
          >
            <option value="Failed">Failed</option>
          </select>
        </div>
      </div>

      {loading ? (
        <p className="mb-4 text-sm text-indigo-600 animate-pulse">
          Loading documents for human review...
        </p>
      ) : (
        message && <p className="mb-4 text-sm text-gray-700">{message}</p>
      )}

      {/* Table */}
      <div className="overflow-x-auto bg-white shadow rounded-lg">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="bg-indigo-50 text-gray-700 text-left">
              <th className="p-3 border-b">#</th>
              <th className="p-3 border-b">Client</th>
              <th className="p-3 border-b">Invoice</th>
              <th className="p-3 border-b">Uploaded On</th>
              <th className="p-3 border-b">Updated On</th>
              <th className="p-3 border-b">Data Extraction</th>
              <th className="p-3 border-b">ERP Entry</th>
              <th className="p-3 border-b">Action</th>
            </tr>
          </thead>

          <tbody>
            {docs.length === 0 ? (
              <tr>
                <td
                  colSpan="8"
                  className="text-center p-4 text-gray-500 italic"
                >
                  No documents require human review
                </td>
              </tr>
            ) : (
              docs.map((doc, index) => (
                <tr key={doc.id ?? doc.doc_id} className="hover:bg-gray-50">
                  <td className="p-3 border-b">{index + 1}</td>
                  <td className="p-3 border-b">{doc.client_name}</td>
                  <td className="p-3 border-b text-indigo-600 underline cursor-pointer">
                    <a
                      href={`${window.location.origin}/invoice/${doc.id ?? doc.doc_id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        const id = doc.id ?? doc.doc_id;
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
                      {getInvoiceText(doc)}
                    </a>
                  </td>
                  <td className="p-3 border-b">
                    {formatDateTime(doc.uploaded_on)}
                  </td>
                  <td className="p-3 border-b">
                    {formatDateTime(doc.updated_at)}
                  </td>
                  <td className="p-3 border-b">
                    <StatusBadge status={doc.data_extraction_status} />
                  </td>
                  <td className="p-3 border-b">
                    <StatusBadge status={doc.erp_entry_status} />
                  </td>
                  <td className="p-3 border-b">
                    <button
                      onClick={() => handleFix(doc)}
                      className="bg-indigo-600 text-white px-3 py-1 rounded hover:bg-indigo-700 text-sm"
                    >
                      Fix
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

