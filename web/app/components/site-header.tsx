import { Github } from "lucide-react";
import { ThemeToggle } from "./theme-toggle";

const links = [
  { href: "#method", label: "Method" },
  { href: "#objects", label: "Objects" },
  { href: "#architecture", label: "Architecture" },
  { href: "#output", label: "Output" }
];

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="wrap header-inner">
        <a href="#top" className="brand-link">
          <span>Rinse</span>
          <span>/</span>
          <span>Data Cleaner</span>
        </a>
        <nav className="nav-links" aria-label="Page navigation">
          {links.map((link) => (
            <a href={link.href} key={link.href}>
              {link.label}
            </a>
          ))}
        </nav>
        <div className="header-actions">
          <ThemeToggle />
          <a className="github-link" href="https://github.com/Hqzdev/Rinse">
            <Github size={14} />
            <span>GitHub</span>
          </a>
        </div>
      </div>
    </header>
  );
}
