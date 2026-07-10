import { afterEach, describe, expect, it, vi } from "vitest";
import { orvalFetcher } from "./orval-fetcher";

describe("orvalFetcher", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns the response envelope expected by Orval 8", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await orvalFetcher<{ data: { status: string }; status: number; headers: Headers }>("/api/v1/healthz");

    expect(result.data).toEqual({ status: "ok" });
    expect(result.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/healthz", expect.objectContaining({ credentials: "include" }));
  });

  it("normalizes API error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { message: "Email or password is incorrect" } }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(orvalFetcher("/api/v1/auth/login")).rejects.toMatchObject({
      status: 401,
      message: "Email or password is incorrect",
    });
  });
});
