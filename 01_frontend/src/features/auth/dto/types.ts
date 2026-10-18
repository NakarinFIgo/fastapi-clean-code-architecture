import type { TokenPair } from "../../../shared/api/types";

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  created_at: string;
  updated_at: string;
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
