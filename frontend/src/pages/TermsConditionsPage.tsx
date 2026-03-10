import { LegalLayout } from "@/components/LegalLayout";

export function TermsConditionsPage() {
  return (
    <LegalLayout>
      <div className="legal-content">
        <section className="legal-section">
          <h2>1. Acceptance of Terms</h2>
          <p>
            By accessing this platform, users agree to these terms and to all company policies governing people analytics,
            security, confidentiality, and acceptable use.
          </p>
        </section>

        <section className="legal-section">
          <h2>2. Authorized Use</h2>
          <p>
            Access is granted only for approved business workflows. Users must not misuse analytics output, bypass controls, or
            access data beyond their assigned role.
          </p>
        </section>

        <section className="legal-section">
          <h2>3. Account Security</h2>
          <p>
            Users are responsible for safeguarding credentials, using strong passwords, and reporting suspicious account activity
            immediately.
          </p>
        </section>

        <section className="legal-section">
          <h2>4. Data Responsibilities</h2>
          <p>
            Data owners must ensure lawful collection and accuracy of workforce records. Platform operators must maintain audit
            logs and protect data integrity for ingestion and analytics pipelines.
          </p>
        </section>

        <section className="legal-section">
          <h2>5. Service Availability</h2>
          <p>
            The service is provided on a best-effort basis for internal operations. Scheduled maintenance, upgrades, and incident
            response activities may temporarily affect availability.
          </p>
        </section>

        <section className="legal-section">
          <h2>6. Prohibited Actions</h2>
          <p>
            Reverse engineering, unauthorized data extraction, credential sharing, and attempts to disable security controls are
            strictly prohibited and may trigger access revocation.
          </p>
        </section>

        <section className="legal-section">
          <h2>7. Limitation of Liability</h2>
          <p>
            Analytics outputs support decision making but do not replace human judgment or legal advice. Final personnel decisions
            remain the responsibility of authorized business stakeholders.
          </p>
        </section>

        <section className="legal-section">
          <h2>8. Changes to Terms</h2>
          <p>
            Terms may be updated as required by legal, regulatory, or operational changes. Continued use after updates constitutes
            acceptance of the revised terms.
          </p>
        </section>
      </div>
    </LegalLayout>
  );
}
