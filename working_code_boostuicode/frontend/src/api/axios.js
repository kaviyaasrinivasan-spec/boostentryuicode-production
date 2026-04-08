import axios from "axios";

const api = axios.create({
  baseURL: "http://103.14.123.44:30010", // Production server
});

export default api;
