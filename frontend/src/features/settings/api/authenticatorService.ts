// frontend/src/features/settings/api/authenticatorService.ts
// Feladat: Authenticator API hívások feature-szintű thin wrappere UI logika nélkül.
// Sárközi Mihály - 2026.05.29

export {
  confirmAuthenticatorSetup,
  disableAuthenticator,
  getAuthenticatorStatus,
  startAuthenticatorSetup,
  type AuthenticatorSetupResponse,
  type AuthenticatorStatusResponse,
} from "../../../api/services/authenticatorService";
