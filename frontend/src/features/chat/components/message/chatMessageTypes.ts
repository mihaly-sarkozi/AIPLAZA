export type ChatSource = {
  kb_uuid: string;
  kb_name?: string;
  point_id: string;
  source_id?: string;
  title?: string;
  snippet?: string;
  source_url?: string;
  source_type?: string;
  file_ref?: string | null;
  display_type?: string;
  created_by?: number | null;
  created_by_label?: string;
  created_at?: string | null;
};

export type RestoredPiiSpan = {
  start: number;
  end: number;
  token?: string;
  value?: string;
  entity_type?: string;
};
