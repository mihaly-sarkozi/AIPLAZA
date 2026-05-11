import api from "../axiosClient";

export type AuthenticatorStatusResponse = {
  enabled: boolean;
  pending: boolean;
};

export type AuthenticatorSetupResponse = {
  enabled: boolean;
  pending: boolean;
  secret: string;
  otpauth_uri: string;
  expires_at: string;
};

export async function getAuthenticatorStatus(): Promise<AuthenticatorStatusResponse> {
  const res = await api.get("/auth/authenticator/status");
  return res.data as AuthenticatorStatusResponse;
}

export async function startAuthenticatorSetup(): Promise<AuthenticatorSetupResponse> {
  const res = await api.post("/auth/authenticator/setup");
  return res.data as AuthenticatorSetupResponse;
}

export async function confirmAuthenticatorSetup(code: string): Promise<AuthenticatorStatusResponse> {
  const res = await api.post("/auth/authenticator/confirm", { code });
  return res.data as AuthenticatorStatusResponse;
}

export async function disableAuthenticator(): Promise<AuthenticatorStatusResponse> {
  const res = await api.delete("/auth/authenticator");
  return res.data as AuthenticatorStatusResponse;
}
