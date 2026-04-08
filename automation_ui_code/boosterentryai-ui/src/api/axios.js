import axios from "axios";

// Using Nginx proxy: /api/* is routed to Flask backend (port 30010)
// No need for explicit host/port - just use relative paths
const api = axios.create({
  baseURL: "",  // Empty = same origin, Nginx routes /api/ to backend
});

export default api;

