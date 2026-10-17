export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  created_at: string;
  updated_at: string;
}

export interface TokenPair {
  access: string;
  refresh: string;
}

export interface LoginResponse {
  user: User;
  token: TokenPair;
}

export interface RegisterInput {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

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
