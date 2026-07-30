import type { Metadata } from "next";
import { SetPasswordView } from "@/components/onboarding/SetPasswordView";

export const metadata: Metadata = {
  title: "Set your password",
  robots: { index: false, follow: false },
};

// Landing page for the link in Firebase's "set your password" email
// (sent by StartFreeModal.tsx via sendPasswordResetEmail with
// actionCodeSettings.url pointed here). Reads oobCode from the query
// string client-side -- see SetPasswordView.
export default function SetPasswordPage() {
  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center bg-[var(--color-ink)] px-4 py-16">
      <SetPasswordView />
    </div>
  );
}
