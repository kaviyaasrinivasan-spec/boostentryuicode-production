import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import api from "../api/axios";

export default function InvoiceView() {
  const { id } = useParams();
  const [doc, setDoc] = useState(null);
  const [jsonData, setJsonData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchDoc = async () => {
      try {
        const res = await api.get(`/api/monitoring/${id}`);
        console.log(`📄 Loaded doc ${id}:`, res.data);

        if (res.data.status !== "success") throw new Error("Failed API response");

        const data = res.data.data;
        setDoc(data.doc);

        // ✅ Directly set extracted_data (array of { field, value })
        setJsonData(data.extracted_data || []);
      } catch (err) {
        console.error("❌ Error loading doc:", err);
        setError("Failed to load document details.");
      } finally {
        setLoading(false);
      }
    };

    fetchDoc();
  }, [id]);

  if (loading)
    return (
      <div className="p-10 text-gray-600 text-center text-lg animate-pulse">
        Loading document #{id}...
      </div>
    );

  if (error)
    return (
      <div className="p-10 text-red-600 text-center text-lg">{error}</div>
    );

  if (!doc)
    return (
      <div className="p-10 text-gray-600 text-center text-lg">
        No document found.
      </div>
    );

  console.log("📂 File URL:", doc?.file_url);

  const StatusBadge = ({ label, status }) => {
    let color =
      status === "Completed"
        ? "bg-green-100 text-green-700"
        : status === "Failed"
        ? "bg-red-100 text-red-700"
        : "bg-yellow-100 text-yellow-700";
    return (
      <span
        className={`px-3 py-1 rounded text-sm font-medium ${color} border border-gray-200`}
      >
        {label}: {status}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* HEADER */}
      <div className="bg-white shadow rounded-xl p-5 mb-6 flex flex-wrap items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-indigo-700 mb-2">
            {doc.client_name || "Unknown Client"} – {doc.doc_type || "Document"}
          </h2>
          <p className="text-sm text-gray-600">
            <strong>Uploaded On:</strong> {doc.uploaded_on || "—"}
          </p>
        </div>

        <div className="flex gap-3 mt-3 md:mt-0">
          <StatusBadge
            label="Data Extraction"
            status={doc.data_extraction_status}
          />
          <StatusBadge label="ERP Entry" status={doc.erp_entry_status} />
        </div>
      </div>

      {/* BODY */}
      <div className="flex flex-col md:flex-row gap-6">
        {/* LEFT SIDE - PDF */}
        <div className="w-full md:w-1/2 bg-white shadow-lg rounded-xl p-4">
          <h3 className="text-indigo-700 font-semibold text-lg mb-3">
            Document Preview
          </h3>
          {doc.file_url ? (
            <iframe
              src={doc.file_url}
              className="w-full h-[80vh] border rounded-lg"
              title={`PDF Preview ${id}`}
            ></iframe>
          ) : (
            <p className="text-sm text-gray-500 text-center italic">
              PDF not available.
            </p>
          )}
        </div>

        {/* RIGHT SIDE - Extracted JSON */}
        <div className="w-full md:w-1/2 bg-white shadow-lg rounded-xl p-6 overflow-y-auto">
          <h3 className="text-indigo-700 font-semibold text-lg mb-4">
            Extracted Data
          </h3>

          {/* ✅ Updated Rendering Logic */}
          {(!jsonData || jsonData.length === 0) ? (
            <p className="text-gray-500 text-sm italic text-center">
              No extracted data available.
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {jsonData.map(({ field, value }, index) => (
                <div key={index}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {field}
                  </label>
                  <input
                    type="text"
                    value={value || ""}
                    readOnly
                    className="w-full border rounded px-3 py-2 text-sm bg-gray-50 text-gray-600"
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
