import { request } from "./client";
import { loadTokens } from "./tokenStore";
import type { Collection, DataList, LoginResponse, RegisterInput, User } from "./types";

export const register = (input: RegisterInput) =>
  request<User>("/users/register", { method: "POST", body: input });

export const login = (email: string, password: string) =>
  request<LoginResponse>("/users/login", { method: "POST", body: { email, password } });

export const profile = () => request<User>("/users/profile", { method: "POST", auth: true });

export const logout = () => {
  const refresh = loadTokens()?.refresh ?? "";
  return request<void>("/users/logout", { method: "POST", body: { refresh_token: refresh } });
};

export const listData = (collection: Collection, page: number, pageSize: number) =>
  request<DataList>(`/data/${collection}/?_page=${page}&_pageSize=${pageSize}`, { auth: true });

export const describe = (collection: Collection) =>
  request<unknown>(`/data/${collection}/describe`, { auth: true });
