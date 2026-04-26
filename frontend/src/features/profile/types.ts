/** Profile feature types. */
export type PatchMePayload = { name?: string | null; preferred_locale?: string; preferred_theme?: string };
export type ChangePasswordPayload = { current_password: string; new_password: string };
