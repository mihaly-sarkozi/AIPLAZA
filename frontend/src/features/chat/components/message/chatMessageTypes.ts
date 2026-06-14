export type ChatSource = {
  kb_uuid: string;
  kb_name?: string;
  point_id: string;
  source_id?: string;
  citation_id?: string;
  title?: string;
  snippet?: string;
  source_url?: string;
  download_url?: string;
  download_url_template?: string;
  download_ref?: string;
  page_numbers?: number[];
  section_title?: string;
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
