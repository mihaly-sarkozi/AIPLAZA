import axios from "axios";
import { useAuthStore } from "../store/authStore";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true, // küldi a HttpOnly cookie-t (refresh tokenhez)
});

// 🔒 Token hozzáadása minden kéréshez
api.interceptors.request.use((config) => {
  const { token } = useAuthStore.getState(); // FIGYELEM: 'token', nem 'accessToken'
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 🔁 Automatikus refresh, ha 401 jön vissza
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        // Friss token kérés
        const refreshResponse = await axios.post(
          `${import.meta.env.VITE_API_URL}/auth/refresh`,
          {},
          { withCredentials: true }
        );

        const newToken = refreshResponse.data.access_token;

        const store = useAuthStore.getState();
        store.setToken(newToken); // állítsuk be az új tokent

        // Új tokennel ismételd meg az eredeti kérést
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        console.warn("Token refresh failed:", refreshError);
        useAuthStore.getState().logout();
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);

export default api;
