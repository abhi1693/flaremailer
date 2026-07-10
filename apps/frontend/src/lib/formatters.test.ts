import { describe, expect, it } from "vitest";
import { initials, recipientOf, splitEmails } from "./formatters";

describe("formatters", () => {
  it("splits comma and whitespace separated recipients", () => {
    expect(splitEmails("ada@example.com, grace@example.com alan@example.com")).toEqual([
      "ada@example.com",
      "grace@example.com",
      "alan@example.com",
    ]);
  });

  it("normalizes recipient lists", () => {
    expect(recipientOf({ id: "1", project_id: "p1", from_email: "from@x.test", subject: "Hi", status: "sent", to: [{ email: "a@x.test" }, { email: "b@x.test" }], tags: [], attempt_count: 1, provider_message_id: null, error_message: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", sent_at: null })).toBe(
      "a@x.test, b@x.test",
    );
  });

  it("creates useful initials", () => {
    expect(initials("Ada Lovelace")).toBe("AL");
    expect(initials("hello@example.com")).toBe("HE");
  });
});
