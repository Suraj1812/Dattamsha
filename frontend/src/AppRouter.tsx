import { Navigate, Route, Routes } from "react-router-dom";

import App from "@/App";
import { PrivacyPolicyPage } from "@/pages/PrivacyPolicyPage";
import { TermsConditionsPage } from "@/pages/TermsConditionsPage";
import { useSessionStore } from "@/store/sessionStore";

export function AppRouter() {
  const isLoggedIn = Boolean(useSessionStore((state) => state.accessToken));

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard/overview" replace />} />
      <Route path="/dashboard" element={<Navigate to="/dashboard/overview" replace />} />
      <Route path="/dashboard/:tab" element={<App />} />
      <Route
        path="/privacy-policy"
        element={isLoggedIn ? <Navigate to="/dashboard/overview" replace /> : <PrivacyPolicyPage />}
      />
      <Route
        path="/terms-and-conditions"
        element={isLoggedIn ? <Navigate to="/dashboard/overview" replace /> : <TermsConditionsPage />}
      />
      <Route path="*" element={<Navigate to="/dashboard/overview" replace />} />
    </Routes>
  );
}
