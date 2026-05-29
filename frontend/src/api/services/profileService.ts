import api from "../axiosClient";

export type ProfilePreferences = {
  dashboard_layout: "comfortable" | "compact";
  show_tips: boolean;
};

export type ProfileResponse = {
  id: number;
  email: string;
  pending_email?: string | null;
  pending_email_expires_at?: string | null;
  role: string;
  is_active: boolean;
  name?: string | null;
  preferred_locale?: string | null;
  preferred_theme?: string | null;
  locale?: string;
  theme?: string;
  credentials_password_set?: boolean;
  tenant_demo_mode?: boolean;
  tenant_kb_has_training?: boolean;
  app_preferences: ProfilePreferences;
};

export type PatchProfilePayload = {
  name?: string | null;
  email?: string;
  preferred_locale?: string;
  preferred_theme?: string;
  app_preferences?: Partial<ProfilePreferences>;
};

export async function getProfile(): Promise<ProfileResponse> {
  const res = await api.get("/profile");
  return res.data as ProfileResponse;
}

export async function patchProfile(body: PatchProfilePayload): Promise<ProfileResponse> {
  const res = await api.patch("/profile", body);
  return res.data as ProfileResponse;
}

export async function getProfilePreferences(): Promise<{ app_preferences: ProfilePreferences }> {
  const res = await api.get("/profile/preferences");
  return res.data as { app_preferences: ProfilePreferences };
}

export async function patchProfilePreferences(
  body: Partial<ProfilePreferences>
): Promise<{ app_preferences: ProfilePreferences }> {
  const res = await api.patch("/profile/preferences", body);
  return res.data as { app_preferences: ProfilePreferences };
}
