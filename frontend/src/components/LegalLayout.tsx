import type { ReactNode } from "react";
import { FileText, LayoutDashboard, ShieldCheck } from "lucide-react";
import { NavLink } from "react-router-dom";

type LegalLayoutProps = {
  children: ReactNode;
};

function routeLinkClass(isActive: boolean): string {
  return `route-link route-link-inline ${isActive ? "active" : ""}`;
}

export function LegalLayout({ children }: LegalLayoutProps) {
  return (
    <div className="legal-shell">
      <div className="legal-body">
        <aside className="legal-sidebar">
          <div className="sidebar-card">
            <p className="sidebar-label">Legal Menu</p>
            <nav className="main-tabs" aria-label="Legal navigation">
              <NavLink to="/dashboard" className={({ isActive }) => routeLinkClass(isActive)}>
                <LayoutDashboard size={16} /> Dashboard
              </NavLink>
              <NavLink to="/privacy-policy" className={({ isActive }) => routeLinkClass(isActive)}>
                <ShieldCheck size={16} /> Privacy Policy
              </NavLink>
              <NavLink to="/terms-and-conditions" className={({ isActive }) => routeLinkClass(isActive)}>
                <FileText size={16} /> Terms & Conditions
              </NavLink>
            </nav>
          </div>
          <div className="sidebar-card">
            <p className="sidebar-label">Effective Date</p>
            <h3>March 10, 2026</h3>
            <p>Review this section with your legal, compliance, and HR operations teams before production deployment.</p>
          </div>
        </aside>

        <main className="legal-main">
          <section className="panel legal-panel">{children}</section>
        </main>
      </div>
    </div>
  );
}
