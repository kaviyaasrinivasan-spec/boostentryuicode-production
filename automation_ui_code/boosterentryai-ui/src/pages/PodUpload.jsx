// src/pages/PodUpload.jsx
// ✅ POD Upload — Professional Clean Edition
// Simplified, Balanced, Neat UI

import { useEffect, useRef, useState } from "react";
import api from "../api/axios";

const MAX_FILES = 20;

const isPdf = (f) =>
    f.type === "application/pdf" ||
    (f.name && f.name.toLowerCase().endsWith(".pdf"));

export default function PodUpload() {
    const [clients, setClients] = useState([]);
    const [formats, setFormats] = useState([]);
    const [selectedClient, setSelectedClient] = useState("");
    const [selectedFormat, setSelectedFormat] = useState("");
    const [filesRecords, setFilesRecords] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const [toast, setToast] = useState(null);

    const fileInputRef = useRef(null);

    // ── Fetch clients ─────────────────────────────────────────────
    useEffect(() => {
        (async () => {
            try {
                const res = await api.get("/api/clients");
                const allClients = res.data.data || [];
                const podClients = allClients.filter(c => c.name.toLowerCase().includes("pod"));
                setClients(podClients);
            } catch (err) { console.error("Error loading clients", err); }
        })();
    }, []);

    // ── Client change → fetch formats ────────────────────────────
    const handleClientChange = async (e) => {
        const cid = e.target.value;
        setSelectedClient(cid);
        setSelectedFormat("");
        setFormats([]);
        if (!cid) return;
        try {
            const res = await api.get(`/api/doc_formats/${cid}`);
            setFormats(res.data.data || []);
        } catch (err) { console.error("Error loading formats", err); }
    };

    // ── Toast ─────────────────────────────────────────────────────
    const showToast = (type, msg) => {
        setToast({ type, msg });
        setTimeout(() => setToast(null), 4000);
    };

    // ── Add files ────────────────────────────────────────────────
    const addFiles = (pickedFiles) => {
        const arr = Array.from(pickedFiles || []);
        if (!arr.length) return;
        const nonPdf = arr.filter((f) => !isPdf(f));
        if (nonPdf.length)
            showToast("warn", `Only PDF files are allowed.`);
        const pdfs = arr.filter((f) => isPdf(f));
        if (!pdfs.length) return;

        setFilesRecords((prev) => {
            const seen = new Set(prev.map((r) => `${r.originalName}|${r.size}`));
            const ts = Date.now();
            const newRecs = pdfs
                .filter((f) => !seen.has(`${f.name}|${f.size}`))
                .map((f, i) => ({
                    id: `${ts}_${i}_${f.name.replace(/\s+/g, "_")}`,
                    file: f,
                    originalName: f.name,
                    size: f.size,
                    progress: 0,
                    status: "queued",
                    message: "",
                }));
            const combined = [...prev, ...newRecs];
            return combined.slice(0, MAX_FILES);
        });
    };

    const handleFileSelect = (e) => { addFiles(e.target.files); e.target.value = ""; };
    const handleDrop = (e) => { e.preventDefault(); setIsDragging(false); addFiles(e.dataTransfer.files); };
    const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
    const handleDragLeave = () => setIsDragging(false);
    const removeFile = (id) => setFilesRecords((p) => p.filter((r) => r.id !== id));
    const clearAll = () => setFilesRecords([]);
    const openPicker = () => fileInputRef.current?.click();

    // ── Upload single file ────────────────────────────────────────
    const uploadSingleFile = async (rec) => {
        setFilesRecords((prev) =>
            prev.map((r) => r.id === rec.id ? { ...r, status: "uploading", progress: 0 } : r)
        );
        const fd = new FormData();
        fd.append("files", rec.file);
        fd.append("client_id", selectedClient);
        fd.append("doc_format_id", selectedFormat);

        try {
            const res = await api.post("/api/pod-upload", fd, {
                headers: { "Content-Type": "multipart/form-data" },
                timeout: 600000, // 10 minutes for heavy PDFs
                onUploadProgress: (ev) => {
                    const pct = ev.total ? Math.round((ev.loaded * 100) / ev.total) : 50;
                    setFilesRecords((prev) =>
                        prev.map((r) => r.id === rec.id ? { ...r, progress: Math.min(pct, 95) } : r)
                    );
                },
            });

            if (res?.data?.status === "success") {
                setFilesRecords((prev) =>
                    prev.map((r) => r.id === rec.id ? { ...r, progress: 100, status: "done" } : r)
                );
                return { ok: true };
            }
            setFilesRecords((prev) =>
                prev.map((r) => r.id === rec.id ? { ...r, status: "error", message: "Failed" } : r)
            );
            return { ok: false };
        } catch (err) {
            setFilesRecords((prev) =>
                prev.map((r) => r.id === rec.id ? { ...r, status: "error", message: "Error" } : r)
            );
            return { ok: false };
        }
    };

    const handleUpload = async (e) => {
        e?.preventDefault?.();
        if (!selectedClient || !selectedFormat || !filesRecords.length) return;

        setUploading(true);
        for (const rec of filesRecords) {
            if (rec.status !== "done") await uploadSingleFile(rec);
        }
        setUploading(false);
        showToast("success", "Upload process complete.");
    };

    const badge = (status) => {
        const cls = {
            queued: "bg-gray-100 text-gray-500",
            uploading: "bg-blue-50 text-blue-600",
            done: "bg-green-50 text-green-600",
            error: "bg-red-50 text-red-600"
        };
        const label = { queued: "Queued", uploading: "Uploading...", done: "Done", error: "Failed" };
        return (
            <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded ${cls[status]}`}>
                {label[status]}
            </span>
        );
    };

    return (
        <div className="mx-auto w-full max-w-3xl px-4 py-8 antialiased text-gray-900 font-sans">

            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">POD Upload</h1>
                    <p className="text-sm text-gray-500 mt-1">Select client and upload your documents</p>
                </div>
            </div>

            {/* Toast */}
            {toast && (
                <div className={`mb-6 p-4 rounded-lg text-sm font-medium shadow-sm border ${toast.type === "success" ? "bg-green-50 border-green-100 text-green-800" : "bg-blue-50 border-blue-100 text-blue-800"
                    }`}>
                    {toast.msg}
                </div>
            )}

            {/* Main Form */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="p-6 md:p-8 space-y-8">

                    {/* Inputs Row */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-gray-700 ml-1">Client Name</label>
                            <select
                                className="w-full h-11 px-4 rounded-lg border border-gray-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all cursor-pointer bg-gray-50/50"
                                value={selectedClient}
                                onChange={handleClientChange}
                            >
                                <option value="">Select a client</option>
                                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                            </select>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-gray-700 ml-1">Document Type</label>
                            <select
                                className="w-full h-11 px-4 rounded-lg border border-gray-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all cursor-pointer bg-gray-50/50 disabled:opacity-50 disabled:cursor-not-allowed"
                                value={selectedFormat}
                                onChange={(e) => setSelectedFormat(e.target.value)}
                                disabled={!selectedClient}
                            >
                                <option value="">Select document type</option>
                                {formats.map(f => <option key={f.id} value={f.id}>{f.doc_type}</option>)}
                            </select>
                        </div>
                    </div>

                    {/* Dropzone */}
                    <div
                        onDrop={handleDrop} onDragOver={handleDragOver} onDragLeave={handleDragLeave}
                        onClick={openPicker}
                        className={`group relative border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer
              ${isDragging ? "bg-blue-50 border-blue-400" : "bg-white border-gray-200 hover:border-blue-300 hover:bg-gray-50/50"}`}
                    >
                        <div className="flex flex-col items-center">
                            <div className="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mb-4 group-hover:bg-blue-100 transition-colors">
                                <svg className="w-6 h-6 text-gray-400 group-hover:text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                            </div>
                            <p className="text-base font-semibold text-gray-700">Drop files here or click to browse</p>
                            <p className="text-xs text-gray-400 mt-1">Maximum 20 PDF files at a time</p>
                        </div>
                        <input ref={fileInputRef} type="file" accept=".pdf" multiple onChange={handleFileSelect} className="hidden" />
                    </div>

                    {/* Queue List */}
                    {filesRecords.length > 0 && (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between px-1">
                                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Files In Queue</h3>
                                <button type="button" onClick={clearAll} className="text-xs font-semibold text-red-500 hover:text-red-600 transition-colors">Clear All</button>
                            </div>
                            <div className="divide-y divide-gray-50 border border-gray-50 rounded-lg overflow-hidden bg-gray-50/30">
                                {filesRecords.map((rec) => (
                                    <div key={rec.id} className="p-3 flex items-center justify-between bg-white/50">
                                        <div className="flex items-center gap-3 overflow-hidden">
                                            <div className="min-w-0">
                                                <p className="text-sm font-medium text-gray-700 truncate">{rec.originalName}</p>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    {badge(rec.status)}
                                                    {rec.status === 'uploading' && <span className="text-[10px] text-gray-400">{rec.progress}%</span>}
                                                </div>
                                            </div>
                                        </div>
                                        <button type="button" onClick={() => removeFile(rec.id)} disabled={uploading} className="p-1.5 text-gray-300 hover:text-red-500 transition-colors">
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Submit Button */}
                    <button
                        onClick={handleUpload}
                        disabled={uploading || !filesRecords.length || !selectedClient || !selectedFormat}
                        className={`w-full h-12 rounded-lg font-bold text-sm transition-all shadow-md active:scale-[0.99]
              ${uploading || !filesRecords.length || !selectedClient || !selectedFormat
                                ? "bg-blue-300 text-white cursor-not-allowed shadow-none"
                                : "bg-blue-600 text-white hover:bg-blue-700 shadow-blue-200"}`}
                    >
                        {uploading ? (
                            <div className="flex items-center justify-center gap-2">
                                <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                                <span>Uploading Documents...</span>
                            </div>
                        ) : (
                            "Upload Documents"
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
