// src/pages/VehicleHire.jsx
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import api from "../api/axios";

export default function VehicleHire() {
    const [docs, setDocs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState("");
    const [showModal, setShowModal] = useState(false);
    const [selectedDoc, setSelectedDoc] = useState(null);
    const [formData, setFormData] = useState({
        advance_amount: "",
        payable_at: "",
        paid_by: "",
        account: "",
        paymode: "",
        filling_station: "",
        slip_no: "",
        slip_date: "",
        qty: "",
        rate: "",
        amount: ""
    });

    // Send Message Modal State
    const [showSendModal, setShowSendModal] = useState(false);
    const [sendMessageDoc, setSendMessageDoc] = useState(null);
    const [phoneNumbers, setPhoneNumbers] = useState({}); // Store phone numbers per doc
    const [sendFormData, setSendFormData] = useState({
        advance_amount: "",
        qty: ""
    });

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

    // ---------------- effects ----------------
    useEffect(() => {
        fetchVehicleHireData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ---------------- api calls ----------------
    const fetchVehicleHireData = async () => {
        setLoading(true);
        setMessage("");
        try {
            // Get data for the last 30 days by default
            const endDate = new Date().toISOString().split("T")[0];
            const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];

            const params = new URLSearchParams();
            params.append("from_date", startDate);
            params.append("to_date", endDate);

            const res = await api.get(`/api/monitoring?${params.toString()}`);
            const allDocs = res.data?.data || [];

            // Filter to show only records where both data extraction and consignment entry are completed
            // AND vehicle hire status is 'Not Started' (ready to be processed)
            const filtered = allDocs.filter(doc =>
                doc.data_extraction_status === "Completed" &&
                doc.erp_entry_status === "Completed" &&
                doc.vehicle_hire_status === "Not Started"
            );

            setDocs(filtered);
            if (filtered.length === 0) {
                setMessage("No documents ready for vehicle hire processing.");
            }
        } catch (err) {
            console.error(err);
            setMessage(err.response?.data?.error || "Failed to fetch data");
        } finally {
            setLoading(false);
        }
    };

    // ---------------- modal handlers ----------------
    const handleCompleteClick = (doc) => {
        setSelectedDoc(doc);
        setFormData({
            advance_amount: "",
            payable_at: "",
            paid_by: "",
            account: "",
            paymode: "",
            filling_station: "",
            slip_no: "",
            slip_date: "",
            qty: "",
            rate: "",
            amount: ""
        });
        setShowModal(true);
    };

    const handleCloseModal = () => {
        setShowModal(false);
        setSelectedDoc(null);
        setFormData({
            advance_amount: "",
            payable_at: "",
            paid_by: "",
            account: "",
            paymode: "",
            filling_station: "",
            slip_no: "",
            slip_date: "",
            qty: "",
            rate: "",
            amount: ""
        });
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            console.log("=== Vehicle Hire Submit ===");
            console.log("selectedDoc:", selectedDoc);
            console.log("formData:", formData);

            const payload = {
                doc_id: parseInt(selectedDoc.id),
                ...formData
            };

            console.log("Payload being sent:", payload);

            const response = await api.post('/api/vehicle-hire', payload);

            if (response.data.success) {
                alert('Data submission is completed');
                handleCloseModal();
                fetchVehicleHireData(); // Refresh data to update the list
            }
        } catch (err) {
            console.error('Error submitting vehicle hire data:', err);
            const errorMsg = err.response?.data?.error || 'Failed to submit vehicle hire data';
            alert(errorMsg);
        }
    };

    // ---------------- Send Message Handlers ----------------
    const getConsignmentNo = (doc) => {
        try {
            const extractedData = parseJsonSafe(doc?.extracted_json);
            const data = unwrapFinalData(extractedData);
            return data.ConsignmentNo || "";
        } catch {
            return "";
        }
    };

    const handleSendClick = (doc) => {
        setSendMessageDoc(doc);
        setSendFormData({
            advance_amount: "",
            qty: ""
        });
        setShowSendModal(true);
    };

    const handleCloseSendModal = () => {
        setShowSendModal(false);
        setSendMessageDoc(null);
        setSendFormData({
            advance_amount: "",
            qty: ""
        });
    };

    const handleSendFormChange = (e) => {
        const { name, value } = e.target;
        setSendFormData(prev => ({
            ...prev,
            [name]: value
        }));
    };

    const handleSendMessage = async () => {
        try {
            const phoneNo = phoneNumbers[sendMessageDoc.id];

            if (!phoneNo) {
                alert("Please enter a phone number");
                return;
            }

            const payload = {
                doc_id: parseInt(sendMessageDoc.id),
                phone_no: phoneNo
            };

            const response = await api.post('/api/vehicle-hire/send-message', payload);

            if (response.data.success) {
                alert(`✅ Session started successfully!\n\nManifest No: ${response.data.manifest_no}\n\nMessage sent to Telegram. The driver will reply with Advance Amount and Quantity.`);
                handleCloseSendModal();
                // Refresh the data to remove this item from the list
                fetchVehicleHireData();
            }
        } catch (err) {
            console.error('Error starting session:', err);
            const errorMsg = err.response?.data?.error || 'Failed to start session';
            alert(errorMsg);
        }
    };
    // ---------------- render ----------------
    return (
        <div className="p-6 max-w-full overflow-x-hidden">
            <h2 className="text-2xl font-semibold text-indigo-700 mb-6">
                Vehicle Hire Processing
            </h2>

            {/* Info message */}
            <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded">
                <p className="text-sm text-blue-800">
                    This page shows documents where both <strong>Data Extraction</strong> and <strong>Consignment Entry</strong> are completed and ready for vehicle hire processing.
                </p>
            </div>

            {/* Loading / Error Message */}
            {loading && (
                <div className="mb-4 p-3 bg-blue-100 text-blue-700 rounded">
                    Loading...
                </div>
            )}
            {!loading && message && (
                <div className="mb-4 p-3 bg-yellow-100 text-yellow-700 rounded">
                    {message}
                </div>
            )}

            {/* Document count */}
            {!loading && docs.length > 0 && (
                <div className="mb-4 text-sm text-gray-600">
                    ✅ Loaded {docs.length} document(s) ready for vehicle hire.
                </div>
            )}

            {/* Table */}
            <div className="overflow-x-auto overflow-y-auto max-h-[600px] bg-white shadow rounded-lg" style={{ scrollbarWidth: 'thin' }}>
                <table className="min-w-full border-collapse">
                    <thead>
                        <tr className="bg-indigo-50 text-gray-700 text-left">
                            <th className="p-3 border-b" style={{ minWidth: '50px' }}>#</th>
                            <th className="p-3 border-b" style={{ minWidth: '140px' }}>Client</th>
                            <th className="p-3 border-b" style={{ minWidth: '120px' }}>Invoice</th>
                            <th className="p-3 border-b" style={{ minWidth: '150px' }}>Action</th>
                            <th className="p-3 border-b" style={{ minWidth: '250px' }}>Send Message</th>
                        </tr>
                    </thead>
                    <tbody>
                        {!loading && docs.length === 0 ? (
                            <tr>
                                <td colSpan="5" className="p-6 text-center text-gray-500">
                                    No records found
                                </td>
                            </tr>
                        ) : (
                            docs.map((doc, idx) => {
                                const invoiceLink = `/invoice/${doc.id}`;
                                const invoiceText = getInvoiceText(doc);
                                return (
                                    <tr key={doc.id || idx} className="hover:bg-gray-50">
                                        <td className="p-3 border-b text-sm">{idx + 1}</td>
                                        <td className="p-3 border-b text-sm">{doc.client_name || "N/A"}</td>
                                        <td className="p-3 border-b text-sm">
                                            <a
                                                href={invoiceLink}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-indigo-600 hover:underline"
                                            >
                                                {invoiceText}
                                            </a>
                                        </td>
                                        <td className="p-3 border-b">
                                            <button
                                                onClick={() => handleCompleteClick(doc)}
                                                className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 transition"
                                            >
                                                Complete
                                            </button>
                                        </td>
                                        <td className="p-3 border-b">
                                            <div className="flex items-center gap-2">
                                                <input
                                                    type="text"
                                                    placeholder="Phone No"
                                                    value={phoneNumbers[doc.id] || ""}
                                                    onChange={(e) => setPhoneNumbers(prev => ({
                                                        ...prev,
                                                        [doc.id]: e.target.value
                                                    }))}
                                                    className="w-28 px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                                />
                                                <button
                                                    onClick={() => handleSendClick(doc)}
                                                    disabled={!phoneNumbers[doc.id]}
                                                    className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed text-sm"
                                                >
                                                    Send
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>

            {/* Modal for Vehicle Hire Form */}
            {showModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
                    <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl my-8">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-xl font-semibold text-gray-800">
                                Vehicle Hire Details
                            </h3>
                            <button
                                onClick={handleCloseModal}
                                className="text-gray-500 hover:text-gray-700"
                            >
                                <X size={24} />
                            </button>
                        </div>

                        <div className="mb-4 p-3 bg-blue-50 rounded">
                            <p className="text-sm text-gray-700">
                                <strong>Client:</strong> {selectedDoc?.client_name}
                            </p>
                            <p className="text-sm text-gray-700">
                                <strong>Invoice:</strong> {getInvoiceText(selectedDoc)}
                            </p>
                        </div>

                        <form onSubmit={handleSubmit}>
                            <div className="grid grid-cols-2 gap-4">
                                {/* Row 1 */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Advance Amount *
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        name="advance_amount"
                                        value={formData.advance_amount}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="Enter amount"
                                    />
                                </div>

                                {/* Row 2 */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Payable At *
                                    </label>
                                    <input
                                        type="text"
                                        name="payable_at"
                                        value={formData.payable_at}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="e.g., BANGALORE"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Paid By *
                                    </label>
                                    <input
                                        type="text"
                                        name="paid_by"
                                        value={formData.paid_by}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="e.g., Bank, Cash"
                                    />
                                </div>

                                {/* Row 3 */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Account *
                                    </label>
                                    <input
                                        type="text"
                                        name="account"
                                        value={formData.account}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="e.g., HDFC BANK A/C-8080"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Pay Mode *
                                    </label>
                                    <input
                                        type="text"
                                        name="paymode"
                                        value={formData.paymode}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="e.g., UPI, NEFT"
                                    />
                                </div>

                                {/* Row 4 */}
                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Filling Station *
                                    </label>
                                    <input
                                        type="text"
                                        name="filling_station"
                                        value={formData.filling_station}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="e.g., KALPATARU FILLING POINT-IOCL"
                                    />
                                </div>

                                {/* Row 5 */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Slip No *
                                    </label>
                                    <input
                                        type="text"
                                        name="slip_no"
                                        value={formData.slip_no}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="Enter slip number"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Slip Date *
                                    </label>
                                    <input
                                        type="date"
                                        name="slip_date"
                                        value={formData.slip_date}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    />
                                </div>

                                {/* Row 6 */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Quantity *
                                    </label>
                                    <input
                                        type="number"
                                        step="0.001"
                                        name="qty"
                                        value={formData.qty}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="Enter quantity"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Rate *
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        name="rate"
                                        value={formData.rate}
                                        onChange={handleInputChange}
                                        required
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="Enter rate"
                                    />
                                </div>

                                {/* Row 7 */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Amount
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        name="amount"
                                        value={formData.amount}
                                        onChange={handleInputChange}
                                        className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="Auto-calculated or manual"
                                    />
                                </div>
                            </div>

                            <div className="mt-6 flex gap-3">
                                <button
                                    type="submit"
                                    className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 transition"
                                >
                                    Submit
                                </button>
                                <button
                                    type="button"
                                    onClick={handleCloseModal}
                                    className="flex-1 px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 transition"
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Send Message Modal */}
            {showSendModal && sendMessageDoc && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
                    <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg my-8">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-xl font-semibold text-gray-800">
                                Start Telegram Session
                            </h3>
                            <button
                                onClick={handleCloseSendModal}
                                className="text-gray-500 hover:text-gray-700"
                            >
                                <X size={24} />
                            </button>
                        </div>

                        <div className="mb-4 p-3 bg-blue-50 rounded">
                            <p className="text-sm text-gray-700">
                                <strong>Client:</strong> {sendMessageDoc?.client_name}
                            </p>
                            <p className="text-sm text-gray-700">
                                <strong>Invoice:</strong> {getInvoiceText(sendMessageDoc)}
                            </p>
                            <p className="text-sm text-gray-700">
                                <strong>Phone:</strong> {phoneNumbers[sendMessageDoc.id]}
                            </p>
                            <p className="text-sm text-gray-700">
                                <strong>Manifest No:</strong> ARAK250{getConsignmentNo(sendMessageDoc)}
                            </p>
                        </div>

                        {/* Instructions */}
                        <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded">
                            <p className="text-sm font-medium text-yellow-800 mb-2">📱 How it works:</p>
                            <ol className="text-sm text-yellow-700 list-decimal list-inside space-y-1">
                                <li>Click "Start Session" below</li>
                                <li>Open the Telegram bot on your phone</li>
                                <li>Click the <strong>"Enter Advance Amount"</strong> button</li>
                                <li>Type the amount and send</li>
                                <li>Click the <strong>"Enter Quantity"</strong> button</li>
                                <li>Type the quantity and send</li>
                                <li>Confirmation message will be sent automatically!</li>
                            </ol>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={handleSendMessage}
                                className="flex-1 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition"
                            >
                                🚀 Start Session
                            </button>
                            <button
                                type="button"
                                onClick={handleCloseSendModal}
                                className="flex-1 px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 transition"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
