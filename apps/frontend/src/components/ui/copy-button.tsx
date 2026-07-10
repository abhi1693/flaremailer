"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export function CopyButton({ value, label = "Copy", copiedLabel = "Copied", variant = "secondary" }: { value: string; label?: string; copiedLabel?: string; variant?: "secondary" | "ghost" }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }
  return <Button type="button" variant={variant} size="sm" icon={copied ? Check : Copy} onClick={copy} aria-label={label || "Copy to clipboard"}>{copied ? copiedLabel : label}</Button>;
}
