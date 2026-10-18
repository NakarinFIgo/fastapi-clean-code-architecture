import { request } from "../../../shared/api/client";
import { loadTokens } from "../../../shared/api/token_store";
import type { LoginResponse, RegisterInput, User } from "../dto/types";

export const register = (input: RegisterInput) =>
  request<User>("/register", { method: "POST", body: input });

export const login = (email: string, password: string) =>
  request<LoginResponse>("/login", { method: "POST", body: { email, password } });

export const profile = () => request<User>("/profile", { method: "POST", auth: true });

export const logout = () => {
  const refresh = loadTokens()?.refresh ?? "";
  return request<void>("/logout", { method: "POST", body: { refresh_token: refresh } });
};
