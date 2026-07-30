import type { Metadata } from "next";
import { CrmDashboard } from "@/components/CrmDashboard";

export const metadata: Metadata = {
  title: "CRM",
  robots: { index: false, follow: false },
};

export default function CrmPage() {
  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">Internal · Admin only</p>
          <h1 className="mt-3 text-hero">CRM</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Every signed-up account and demo request, merged by email. Sign-in required and checked
            against an admin allowlist server-side — this is real auth, not just an unlinked URL (see
            docs/PRD_SIGNUP_CRM.md).
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <CrmDashboard />
      </div>
    </div>
  );
}
