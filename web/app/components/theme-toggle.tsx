"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    const stored = window.localStorage.getItem("rinse-theme");
    const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    const resolved = stored ?? preferred;
    setTheme(resolved);
    document.documentElement.dataset.theme = resolved;
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("rinse-theme", nextTheme);
  }

  return (
    <button className="icon-button" type="button" onClick={toggleTheme} aria-label="Toggle theme">
      {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}
