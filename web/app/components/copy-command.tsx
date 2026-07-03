"use client";

import { Clipboard, Check } from "lucide-react";
import { useState } from "react";

const command = "rinse clean dirty.csv --out clean.json --report report.json";

export function CopyCommand() {
  const [copied, setCopied] = useState(false);

  async function copyCommand() {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <button className="command-button" type="button" onClick={copyCommand}>
      <span>$</span>
      <code>{command}</code>
      {copied ? <Check size={14} /> : <Clipboard size={14} />}
    </button>
  );
}
