// src/pages/Upload.jsx
import { useEffect, useRef, useState } from "react";
import api from "../api/axios";

/**
 * Upload.jsx — responsive & mobile-friendly file list
 * Fix: prevents generated filename overflow by forcing breaks (word-break: break-all)
 * - Drag & drop + file picker (no camera)
 * - Sequential uploads, per-file progress
 * - Uses server final_name as generatedName (handles array/object)
 */

export default function Upload() {
  const [clients, setClients] = useState([]);
  const [formats, setFormats] = useState([]);
  const [selectedClient, setSelectedClient] = useState("");
  const [selectedFormat, setSelectedFormat] = useState("");
  const [filesRecords, setFilesRecords] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef(null);
  const dropRef = useRef(null);

  const ALLOWED_TYPES = [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
    "image/tiff",
  ];
  const isAllowed = (f) => ALLOWED_TYPES.includes(f.type) || f.type === "";

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get("/api/clients");
        const allClients = res.data.data || [];
        const normalClients = allClients.filter(c => !c.name.toLowerCase().includes("pod"));
        setClients(normalClients);
      } catch (err) {
        console.error("Error loading clients", err);
      }
    })();
  }, []);

  const handleClientChange = async (e) => {
    const cid = e.target.value;
    setSelectedClient(cid);
    setSelectedFormat("");
    setFormats([]);
    if (!cid) return;
    try {
      const res = await api.get(`/api/doc_formats/${cid}`);
      setFormats(res.data.data || []);
    } catch (err) {
      console.error("Error loading formats", err);
    }
  };

  // Add files (basic duplicate prevention by name+size)
  const addFiles = (pickedFiles) => {
    const arr = Array.from(pickedFiles || []);
    if (!arr.length) return;
    setFilesRecords((prev) => {
      const seen = new Set(prev.map((r) => `${r.originalName}|${r.size}`));
      const ts = Date.now();
      const newRecs = arr
        .filter((f) => !seen.has(`${f.name}|${f.size}`))
        .map((f, i) => ({
          id: `${ts}_${i}_${(f.name || "file").replace(/\s+/g, "_")}`,
          file: f,
          originalName: f.name || "file",
          generatedName: null,
          size: f.size || 0,
          type: f.type || "",
          progress: 0,
          status: "queued", // queued | uploading | done | error
          message: "",
        }));
      return [...prev, ...newRecs];
    });
  };

  const handleFileSelect = (e) => {
    addFiles(e.target.files);
    e.target.value = "";
  };

  // drag & drop handlers
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  };
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const handleDragLeave = () => setIsDragging(false);

  const removeFile = (id) => setFilesRecords((p) => p.filter((r) => r.id !== id));

  // overall progress (average)
  const overallProgress = (() => {
    if (!filesRecords.length) return 0;
    const sum = filesRecords.reduce((s, r) => s + (r.progress || 0), 0);
    return Math.round(sum / filesRecords.length);
  })();

  // upload single file and set generatedName from server
  const uploadSingleFile = async (rec) => {
    setFilesRecords((prev) => prev.map((r) => (r.id === rec.id ? { ...r, status: "uploading", progress: 0, message: "" } : r)));

    const fd = new FormData();
    fd.append("client_id", selectedClient);
    fd.append("doc_format_id", selectedFormat);
    fd.append("uploaded_by", "senthil"); // change to real user info when available
    fd.append("files", rec.file);

    try {
      const res = await api.post("/api/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (ev) => {
          try {
            const { loaded, total } = ev;
            const pct = total ? Math.round((loaded * 100) / total) : 50;
            setFilesRecords((prev) => prev.map((r) => (r.id === rec.id ? { ...r, progress: pct } : r)));
          } catch (e) {
            // ignore progress calculation errors
          }
        },
        timeout: 5 * 60 * 1000,
      });

      const serverData = res?.data?.data;
      const finalName = Array.isArray(serverData) ? serverData?.[0]?.final_name : serverData?.final_name;

      if (res?.data?.status === "success" && finalName) {
        setFilesRecords((prev) =>
          prev.map((r) =>
            r.id === rec.id
              ? { ...r, progress: 100, status: "done", generatedName: finalName, message: "" }
              : r
          )
        );
        return { ok: true, finalName };
      }

      if (res?.data?.status === "success") {
        setFilesRecords((prev) => prev.map((r) => (r.id === rec.id ? { ...r, progress: 100, status: "done", message: "" } : r)));
        return { ok: true, finalName: null };
      }

      const msg = res?.data?.message || "Unknown server error";
      setFilesRecords((prev) => prev.map((r) => (r.id === rec.id ? { ...r, status: "error", message: msg } : r)));
      return { ok: false, error: msg };
    } catch (err) {
      const errMsg = err?.response?.data?.message || err.message || "Network error";
      setFilesRecords((prev) => prev.map((r) => (r.id === rec.id ? { ...r, status: "error", message: errMsg, progress: 0 } : r)));
      return { ok: false, error: errMsg };
    }
  };

  // upload all sequentially
  const handleUpload = async (e) => {
    e?.preventDefault?.();

    if (!selectedClient || !selectedFormat || filesRecords.length === 0) {
      console.warn("Select client, format and at least one file.");
      return;
    }

    const bad = filesRecords.filter((r) => !isAllowed(r.file));
    if (bad.length) {
      console.warn("Unsupported file types:", bad.map((b) => b.originalName).join(", "));
      return;
    }

    setUploading(true);
    try {
      for (const rec of filesRecords) {
        if (rec.status === "done") continue;
        // eslint-disable-next-line no-await-in-loop
        await uploadSingleFile(rec);
      }
    } finally {
      setUploading(false);
    }
  };

  const openFilePicker = () => fileInputRef.current?.click();

  const niceBytes = (n) => {
    if (!Number.isFinite(n)) return "-";
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
    return `${Math.round((n / (1024 * 1024)) * 10) / 10} MB`;
  };

  return (
    <div className="mx-auto w-full md:max-w-4xl px-2 md:px-0">
      <h2 className="text-2xl md:text-3xl font-semibold text-indigo-700 mb-6 text-center md:text-left">Document Upload Center</h2>

      <form onSubmit={handleUpload} className="bg-white p-4 md:p-6 rounded-2xl shadow-lg space-y-5">
        {/* Selectors */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block mb-2 font-medium text-gray-800">Select Client</label>
            <select className="w-full border rounded px-3 py-2 focus:ring-2 focus:ring-indigo-400" value={selectedClient} onChange={handleClientChange}>
              <option value="">-- Choose Client --</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>

          <div>
            <label className="block mb-2 font-medium text-gray-800">Select Document Type</label>
            <select className="w-full border rounded px-3 py-2 focus:ring-2 focus:ring-indigo-400" value={selectedFormat} onChange={(e) => setSelectedFormat(e.target.value)} disabled={!selectedClient}>
              <option value="">-- Choose Format --</option>
              {formats.map((f) => <option key={f.id} value={f.id}>{f.doc_type}</option>)}
            </select>
          </div>
        </div>

        {/* Capture Tips */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-4 mb-4">
          <div className="flex items-start gap-3">
            <div className="text-2xl">📸</div>
            <div>
              <h3 className="font-semibold text-gray-800 mb-1">Capture Tips for Best Results</h3>
              <ul className="text-sm text-gray-600 space-y-1">
                <li className="flex items-center gap-2">
                  <span className="text-green-500">✓</span>
                  <span>Hold camera <strong>directly above</strong> the document (not at an angle)</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-green-500">✓</span>
                  <span>Ensure <strong>good lighting</strong> - avoid shadows on text</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-green-500">✓</span>
                  <span>Keep the document <strong>flat and straight</strong> - no skew or tilt</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-red-500">✗</span>
                  <span className="text-gray-500">Avoid blurry images, curved pages, or partial captures</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Dropzone */}
        <div ref={dropRef} onDrop={handleDrop} onDragOver={handleDragOver} onDragLeave={handleDragLeave}
          className={`border-2 border-dashed rounded-2xl p-5 text-center transition ${isDragging ? "border-indigo-500 bg-indigo-50" : "border-gray-200"}`}>
          <p className="text-gray-600 mb-2">{isDragging ? "Release to upload files" : "Drag and drop one or more invoices here"}</p>
          <p className="text-sm text-gray-500 mb-4">PDF, JPG, PNG, WEBP, TIFF, BMP</p>

          <div className="flex justify-center">
            <button type="button" onClick={openFilePicker} className="px-6 py-2 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-400">
              Choose Files
            </button>
          </div>

          <input ref={fileInputRef} type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,application/pdf,image/*"
            multiple onChange={handleFileSelect} className="hidden" />
        </div>

        {/* File list — scrollable, responsive rows */}
        {filesRecords.length > 0 && (
          <div className="border border-gray-200 rounded-lg p-3 bg-gray-50 max-h-[55vh] md:max-h-96 overflow-auto">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-medium text-gray-700">Selected Files ({filesRecords.length})</div>
              <div className="text-sm text-gray-600">Overall: {overallProgress}%</div>
            </div>

            <ul className="space-y-3">
              {filesRecords.map((rec, i) => (
                <li key={rec.id} className="bg-white p-3 rounded shadow-sm">
                  {/* responsive grid: stack on small, columns on md+ */}
                  <div className="grid grid-cols-1 md:grid-cols-6 gap-3 items-start">
                    {/* Left content (filename + meta + progress) spans 5 cols on md */}
                    <div className="md:col-span-5 min-w-0">
                      {/* filename */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          {rec.generatedName ? (
                            <>
                              <div
                                className="text-sm font-medium text-gray-800"
                                style={{ wordBreak: "break-all", overflowWrap: "anywhere" }}
                              >
                                {rec.generatedName}
                              </div>
                              <div className="text-xs text-gray-400 mt-1 truncate">({rec.originalName})</div>
                            </>
                          ) : (
                            <div
                              className="text-sm font-medium text-gray-800"
                              style={{ wordBreak: "break-all", overflowWrap: "anywhere" }}
                            >
                              {rec.originalName}
                            </div>
                          )}
                        </div>

                        {/* size shown on same row on md and below it will wrap */}
                        <div className="text-xs text-gray-500 md:ml-2 whitespace-nowrap">{niceBytes(rec.size)}</div>
                      </div>

                      {/* meta + progress */}
                      <div className="mt-3">
                        <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
                          <div>{rec.status === "queued" ? "Queued" : rec.status === "uploading" ? "Uploading..." : rec.status === "done" ? "Completed" : "Error"}</div>
                          <div>{rec.progress}%</div>
                        </div>

                        {/* contained progress bar */}
                        <div className="w-full bg-gray-100 rounded h-2 overflow-hidden">
                          <div style={{ width: `${Math.max(0, Math.min(100, rec.progress))}%` }}
                            className={`h-2 rounded ${rec.progress >= 90 ? "bg-green-600" : rec.progress >= 70 ? "bg-green-400" : rec.progress >= 40 ? "bg-yellow-400" : "bg-red-400"}`} />
                        </div>

                        {rec.message && <div className="text-xs text-gray-600 mt-2">{rec.message}</div>}

                        {/* generated filename badge — wrap safely and can't overflow */}
                        {rec.generatedName && (
                          <div className="mt-2 inline-flex items-center gap-2 text-sm text-green-700"
                            style={{ wordBreak: "break-all", overflowWrap: "anywhere", maxWidth: "100%" }}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6L9 17l-5-5" /></svg>
                            <div style={{ maxWidth: "100%" }}>{rec.generatedName}</div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right column — remove button (md visible alongside), on small it will appear below via grid stacking */}
                    <div className="md:col-span-1 flex md:flex-col items-start md:items-end justify-between md:justify-end gap-3">
                      <div className="text-xs text-gray-500 md:hidden">{niceBytes(rec.size)}</div>
                      <button type="button" onClick={() => removeFile(rec.id)} disabled={uploading && rec.status === "uploading"}
                        className={`text-sm ${uploading && rec.status === "uploading" ? "text-gray-300 cursor-not-allowed" : "text-red-500 hover:text-red-700"}`}>
                        Remove
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action button */}
        <div className="pt-2">
          <button type="submit" disabled={uploading || filesRecords.length === 0}
            className={`w-full py-3 rounded-lg text-white font-medium ${uploading ? "bg-gray-400 cursor-not-allowed" : "bg-indigo-600 hover:bg-indigo-700"}`}>
            {uploading ? `Uploading... (${overallProgress}%)` : filesRecords.length > 0 ? "Start Upload" : "Select Files"}
          </button>
        </div>
      </form>
    </div>
  );
}
