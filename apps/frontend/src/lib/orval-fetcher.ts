import { ApiError } from "./api-error";

export async function orvalFetcher<T>(url: string, init: RequestInit = {}): Promise<T> {
  const { headers, ...options } = init;
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    throw ApiError.fromResponse(response.status, body);
  }

  const body = response.status === 204 ? undefined : await response.json();
  return { data: body, status: response.status, headers: response.headers } as T;
}
