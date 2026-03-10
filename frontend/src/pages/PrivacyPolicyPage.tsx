import { LegalLayout } from "@/components/LegalLayout";

export function PrivacyPolicyPage() {
  return (
    <LegalLayout>
      <div className="legal-content">
        <section className="legal-section">
          <h2>1. Scope</h2>
          <p>
            This policy applies to all users and customers using the Dattamsha Workforce Intelligence platform, including
            administrators, HR teams, managers, analysts, and employees.
          </p>
        </section>

        <section className="legal-section">
          <h2>2. Data We Process</h2>
          <p>
            The platform processes employee master data, engagement metrics, workload metrics, performance indicators,
            collaboration metadata, and operational audit events required for security and compliance.
          </p>
        </section>

        <section className="legal-section">
          <h2>3. Purpose of Processing</h2>
          <p>
            Data is used to generate workforce analytics, risk detection, nudges, leadership dashboards, and compliance logs.
            Processing is limited to legitimate organizational and legal purposes.
          </p>
        </section>

        <section className="legal-section">
          <h2>4. Access Controls</h2>
          <p>
            Access is enforced via role-based permissions and authenticated sessions. Users can only access data and actions
            granted to their assigned role.
          </p>
        </section>

        <section className="legal-section">
          <h2>5. Security Measures</h2>
          <p>
            The platform uses encrypted transport channels, password hashing, token-based authentication, audit trails, and
            restricted administrative controls for sensitive operations.
          </p>
        </section>

        <section className="legal-section">
          <h2>6. Data Retention</h2>
          <p>
            Data is retained only for the minimum duration required by business, legal, and regulatory obligations. Expired or
            unnecessary data should be purged through controlled retention workflows.
          </p>
        </section>

        <section className="legal-section">
          <h2>7. Employee Rights</h2>
          <p>
            Organizations should provide access, correction, and deletion request handling in line with local labor and data
            protection laws. Consent controls should be enabled where required.
          </p>
        </section>

        <section className="legal-section">
          <h2>8. Contact</h2>
          <p>
            For privacy requests or incidents, contact your internal Data Protection Officer and HR security owner through
            approved support channels.
          </p>
        </section>
      </div>
    </LegalLayout>
  );
}
