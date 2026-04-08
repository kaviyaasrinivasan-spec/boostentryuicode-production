import { useState, useEffect } from "react";
import api from "../api/axios";
import { Trash2, Edit2, Plus, X, Check } from "lucide-react";

export default function DataTransformation() {
  const [transformations, setTransformations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [stats, setStats] = useState(null);
  
  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    field_name: "",
    from_value: "",
    to_value: ""
  });

  // Filter state
  const [filterField, setFilterField] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    fetchTransformations();
    fetchStats();
  }, []);

  const fetchTransformations = async () => {
    setLoading(true);
    setMessage("");
    try {
      const res = await api.get("/api/transformations");
      if (res.data.success) {
        setTransformations(res.data.data || []);
        setMessage(`✅ Loaded ${res.data.count || 0} transformation(s).`);
      } else {
        setMessage("❌ Failed to load transformations.");
      }
    } catch (err) {
      console.error("❌ Error fetching transformations:", err);
      setMessage("❌ Failed to load transformations.");
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await api.get("/api/transformations/stats");
      if (res.data.success) {
        setStats(res.data.data);
      }
    } catch (err) {
      console.error("Error fetching stats:", err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.field_name || !formData.from_value || !formData.to_value) {
      setMessage("❌ All fields are required!");
      return;
    }

    setLoading(true);
    setMessage("");
    
    try {
      if (editingId) {
        // Update existing
        const res = await api.put(`/api/transformations/${editingId}`, formData);
        if (res.data.success) {
          setMessage("✅ Transformation updated successfully!");
          resetForm();
          fetchTransformations();
          fetchStats();
        } else {
          setMessage(`❌ ${res.data.error || "Failed to update transformation"}`);
        }
      } else {
        // Create new
        const res = await api.post("/api/transformations", formData);
        if (res.data.success) {
          setMessage("✅ Transformation created successfully!");
          resetForm();
          fetchTransformations();
          fetchStats();
        } else {
          setMessage(`❌ ${res.data.error || "Failed to create transformation"}`);
        }
      }
    } catch (err) {
      console.error("❌ Error saving transformation:", err);
      setMessage("❌ Failed to save transformation.");
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (item) => {
    setFormData({
      field_name: item.field_name,
      from_value: item.from_value,
      to_value: item.to_value
    });
    setEditingId(item.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm("Are you sure you want to delete this transformation?")) {
      return;
    }

    setLoading(true);
    setMessage("");
    
    try {
      const res = await api.delete(`/api/transformations/${id}`);
      if (res.data.success) {
        setMessage("✅ Transformation deleted successfully!");
        fetchTransformations();
        fetchStats();
      } else {
        setMessage(`❌ ${res.data.error || "Failed to delete transformation"}`);
      }
    } catch (err) {
      console.error("❌ Error deleting transformation:", err);
      setMessage("❌ Failed to delete transformation.");
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      field_name: "",
      from_value: "",
      to_value: ""
    });
    setEditingId(null);
    setShowForm(false);
  };

  // Get unique field names for filter
  const uniqueFields = [...new Set(transformations.map(t => t.field_name))].sort();

  // Filter transformations
  const filteredTransformations = transformations.filter(item => {
    const matchesField = filterField === "all" || item.field_name === filterField;
    const matchesSearch = 
      searchTerm === "" ||
      item.from_value.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.to_value.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.field_name.toLowerCase().includes(searchTerm.toLowerCase());
    
    return matchesField && matchesSearch;
  });

  const formatDateTime = (dateStr) => {
    if (!dateStr) return "—";
    try {
      return new Date(dateStr).toLocaleString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Data Transformation</h1>
        <p className="text-gray-600 mt-2">
          Manage field value transformations for automated data processing
        </p>
      </div>

      {/* Statistics Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-medium text-gray-600">Total Transformations</h3>
            <p className="text-3xl font-bold text-blue-600 mt-2">{stats.total}</p>
          </div>
          
          {stats.by_field && stats.by_field.map((item, idx) => (
            <div key={idx} className="bg-white rounded-lg shadow p-4">
              <h3 className="text-sm font-medium text-gray-600">{item.field}</h3>
              <p className="text-3xl font-bold text-green-600 mt-2">{item.count}</p>
            </div>
          ))}
        </div>
      )}

      {/* Message */}
      {message && (
        <div className={`mb-4 p-3 rounded ${
          message.includes("✅") ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
        }`}>
          {message}
        </div>
      )}

      {/* Add/Edit Form */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-800">
            {editingId ? "Edit Transformation" : "Add New Transformation"}
          </h2>
          {!showForm && (
            <button
              onClick={() => setShowForm(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus size={20} />
              Add New
            </button>
          )}
        </div>

        {showForm && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Field Name *
                </label>
                <select
                  value={formData.field_name}
                  onChange={(e) => setFormData({ ...formData, field_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select Field</option>
                  <option value="Branch">Branch</option>
                  <option value="ConsignmentNo">ConsignmentNo</option>
                  <option value="Source">Source</option>
                  <option value="Destination">Destination</option>
                  <option value="Vehicle">Vehicle</option>
                  <option value="Consignor">Consignor</option>
                  <option value="Consignee">Consignee</option>
                  <option value="Delivery Address">Delivery Address</option>
                  <option value="Invoice No">Invoice No</option>
                  <option value="ContentName">ContentName</option>
                  <option value="ActualWeight">ActualWeight</option>
                  <option value="Get Rate">Get Rate</option>
                  <option value="GoodsType">GoodsType</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  From Value *
                </label>
                <input
                  type="text"
                  value={formData.from_value}
                  onChange={(e) => setFormData({ ...formData, from_value: e.target.value })}
                  placeholder="Original value"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  To Value *
                </label>
                <input
                  type="text"
                  value={formData.to_value}
                  onChange={(e) => setFormData({ ...formData, to_value: e.target.value })}
                  placeholder="Transformed value"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={loading}
                className="flex items-center gap-2 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                <Check size={20} />
                {editingId ? "Update" : "Create"}
              </button>
              
              <button
                type="button"
                onClick={resetForm}
                className="flex items-center gap-2 px-6 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600"
              >
                <X size={20} />
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Filter by Field
            </label>
            <select
              value={filterField}
              onChange={(e) => setFilterField(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Fields</option>
              {uniqueFields.map(field => (
                <option key={field} value={field}>{field}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Search
            </label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search values..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Transformations Table */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="text-center p-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="mt-2 text-gray-600">Loading...</p>
            </div>
          ) : filteredTransformations.length === 0 ? (
            <div className="text-center p-8 text-gray-500">
              No transformations found.
            </div>
          ) : (
            <table className="min-w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="p-3 text-left border-b font-semibold text-gray-700">S.No</th>
                  <th className="p-3 text-left border-b font-semibold text-gray-700">Field Name</th>
                  <th className="p-3 text-left border-b font-semibold text-gray-700">From Value</th>
                  <th className="p-3 text-left border-b font-semibold text-gray-700">To Value</th>
                  <th className="p-3 text-left border-b font-semibold text-gray-700">Created At</th>
                  <th className="p-3 text-left border-b font-semibold text-gray-700">Updated At</th>
                  <th className="p-3 text-left border-b font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTransformations.map((item, index) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="p-3 border-b">{index + 1}</td>
                    <td className="p-3 border-b">
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                        {item.field_name}
                      </span>
                    </td>
                    <td className="p-3 border-b font-mono text-sm">{item.from_value}</td>
                    <td className="p-3 border-b font-mono text-sm text-green-700 font-semibold">
                      {item.to_value}
                    </td>
                    <td className="p-3 border-b text-sm text-gray-600">
                      {formatDateTime(item.created_at)}
                    </td>
                    <td className="p-3 border-b text-sm text-gray-600">
                      {formatDateTime(item.updated_at)}
                    </td>
                    <td className="p-3 border-b">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleEdit(item)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded"
                          title="Edit"
                        >
                          <Edit2 size={18} />
                        </button>
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded"
                          title="Delete"
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Results Count */}
      {!loading && (
        <div className="mt-4 text-sm text-gray-600 text-center">
          Showing {filteredTransformations.length} of {transformations.length} transformation(s)
        </div>
      )}
    </div>
  );
}
