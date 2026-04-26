/**
 * Re-export auth store from feature. Kept for shared api/axiosClient and backward compatibility.
 */
export { useAuthStore, isDemoInitialPasswordMode, type User } from "../features/auth/state/authStore";
