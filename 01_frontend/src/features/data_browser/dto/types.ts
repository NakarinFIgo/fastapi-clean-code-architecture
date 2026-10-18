export type Row = Record<string, unknown>;

export interface DataList {
  code: number;
  data: Row[];
  page: number;
  page_size: number;
  total_page: number;
  total_data: number;
  message: string;
  data_schema: unknown;
}

export type Collection = "users" | "user-permissions";
