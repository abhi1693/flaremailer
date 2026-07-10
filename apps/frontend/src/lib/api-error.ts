export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  static fromResponse(status: number, body: unknown) {
    const payload = body as
      | {
          detail?: string | Array<{ msg?: string }>;
          message?: string;
          error?: { code?: string; message?: string; details?: unknown };
        }
      | undefined;
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg).filter(Boolean).join(", ")
          : payload?.message ?? payload?.error?.message;

    return new ApiError(
      message || (status === 401 ? "Your session has expired." : "The request could not be completed."),
      status,
      payload?.error?.details ?? body,
      payload?.error?.code,
    );
  }
}

export function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}
