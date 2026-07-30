"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { useFirebaseAuth } from "@/components/FirebaseAuthProvider";
import { ProfileCaptureModal } from "./ProfileCaptureModal";
import {
  fetchMyProfile,
  saveMyProfile,
  PROFILE_SYNC_EVENT,
  type ProfileSyncDetail,
  type UserProfileUpdate,
} from "@/lib/userProfile";

// Mounted inside components/FirebaseAuthProvider.tsx, only in the branch
// where Firebase config exists -- useFirebaseAuth() throws without a
// <FirebaseAuthProvider> ancestor.

const TERRITORY_KEY = "specindex:territory";
const CATEGORY_KEY = "specindex:category";

function readStoredList(key: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function syncProfileToStorage(territory: string[], category: string) {
  window.localStorage.setItem(TERRITORY_KEY, JSON.stringify(territory));
  window.localStorage.setItem(CATEGORY_KEY, category);
  window.dispatchEvent(
    new CustomEvent<ProfileSyncDetail>(PROFILE_SYNC_EVENT, { detail: { territory, category } }),
  );
}

export function AuthSync() {
  const { isLoaded, isSignedIn, getToken, user } = useFirebaseAuth();
  // Snapshot of the page the visitor was on the moment sign-in resolved --
  // a coarse but zero-friction lead_source, distinct from the demo form's
  // source_path (which is more directly the page they clicked "Request
  // Demo" from).
  const pathname = usePathname();
  const wasSignedIn = useRef<boolean | null>(null);
  const checkedThisSignIn = useRef(false);
  const [showModal, setShowModal] = useState(false);
  const [prefill, setPrefill] = useState({ territory: [] as string[], category: "all" });

  // Sign-out cleanup: a signed-out browser (shared machine, or a different
  // account signing in next) must not inherit the last signed-in user's
  // territory/category. Only fires on a true -> false transition, never on
  // initial mount as signed-out.
  useEffect(() => {
    if (!isLoaded) return;
    if (wasSignedIn.current === true && isSignedIn === false) {
      window.localStorage.removeItem(TERRITORY_KEY);
      window.localStorage.removeItem(CATEGORY_KEY);
      checkedThisSignIn.current = false;
      setShowModal(false);
    }
    wasSignedIn.current = isSignedIn ?? null;
  }, [isLoaded, isSignedIn]);

  // On sign-in, check the server profile once. Onboarded -> server wins,
  // overwrite localStorage (not merge). Not onboarded -> open the capture
  // modal, pre-filled from any existing anonymous localStorage state.
  // Not dismissible -- a new account isn't usable until this completes
  // (docs/architecture-2026/02-identity-portals.md onboarding revision:
  // an incomplete profile shows an empty, useless product on first login,
  // which hurts conversion more than a short mandatory form).
  useEffect(() => {
    if (!isLoaded || !isSignedIn || checkedThisSignIn.current) return;
    checkedThisSignIn.current = true;
    fetchMyProfile(getToken)
      .then((profile) => {
        if (profile.onboarded) {
          syncProfileToStorage(profile.territory_states, profile.categories[0] ?? "all");
          return;
        }
        setPrefill({
          territory: readStoredList(TERRITORY_KEY),
          category: window.localStorage.getItem(CATEGORY_KEY) ?? "all",
        });
        setShowModal(true);
      })
      .catch(() => {});
  }, [isLoaded, isSignedIn, getToken]);

  if (!showModal) return null;

  return (
    <ProfileCaptureModal
      initialTerritory={prefill.territory}
      initialCategory={prefill.category}
      fullName={user?.displayName ?? null}
      leadSource={pathname}
      onSubmit={async (body: UserProfileUpdate) => {
        await saveMyProfile(getToken, body);
        syncProfileToStorage(body.territory_states, body.categories[0] ?? "all");
        setShowModal(false);
      }}
    />
  );
}
