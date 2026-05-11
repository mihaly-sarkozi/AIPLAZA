/** Auth feature types. */
export type LoginResponse = {
  access_token?: string;
  pending_token?: string;
  challenge_type?: "email" | "authenticator";
};
export type ForgotPasswordResponse = { ok?: boolean };
export type DefaultSettings = { locale?: string; theme?: string };
