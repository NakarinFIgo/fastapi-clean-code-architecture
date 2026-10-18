import { request } from "../../../shared/api/client";
import type { Collection, DataList } from "../dto/types";

export const listData = (collection: Collection, page: number, pageSize: number) =>
  request<DataList>(`/data/${collection}/?_page=${page}&_pageSize=${pageSize}`, { auth: true });

export const describe = (collection: Collection) =>
  request<unknown>(`/data/${collection}/describe`, { auth: true });
