import type { Metadata } from "next";
import { CustomerDetail } from "@/components/CustomerDetail";

export const metadata: Metadata = {
  title: "View as customer",
  robots: { index: false, follow: false },
};

export default function CustomerDetailPage() {
  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">Internal · Admin only</p>
          <h1 className="mt-3 text-hero">View as customer</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Read-only lookup of one signed-in account&apos;s profile and tracked pipeline. This
            never mints a session as that user or lets you act on their behalf — it&apos;s a
            query, not a login (see docs/architecture-2026/02-identity-portals.md).
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <CustomerDetail />
      </div>
    </div>
  );
}
