import type { Metadata } from "next";
import { AccountSettings } from "@/components/AccountSettings";

export const metadata: Metadata = {
  title: "Account",
  robots: { index: false, follow: false },
};

export default function AccountPage() {
  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-4xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">Account</p>
          <h1 className="mt-3 text-hero">Account settings</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Update your territory, product categories, and contact details. Changes take effect
            immediately across the site.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-4xl px-5 py-10 md:px-8 md:py-12">
        <AccountSettings />
      </div>
    </div>
  );
}
