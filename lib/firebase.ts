// Firebase client SDK init. Only ever touched from the browser (this file
// has no server-side usage) -- the site is a fully static Next.js export
// with no Node server, so Firebase Auth's client SDK (which talks to
// Google's Identity Platform directly from the browser) is a natural fit,
// same reasoning that ruled out @clerk/nextjs in favor of @clerk/clerk-react
// before this swap. Uses the same GCP project ("specindex-ai") already
// backing Postgres/Cloud Run/Vertex, so this is one fewer project to manage,
// not an additional one.
//
// All NEXT_PUBLIC_FIREBASE_* values are public client config (safe to ship
// in the bundle -- Firebase's security model relies on Firestore/Auth rules
// and backend token verification, not on hiding these), sourced from
// Firebase Console -> Project Settings -> General -> Your apps -> Web app.

import { initializeApp, getApps, type FirebaseOptions } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig: FirebaseOptions = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  // Not read by anything today (no Storage/Messaging usage yet) -- included
  // because they're part of the real project config and cost nothing to
  // carry, so a future feature that needs them doesn't need a second config
  // pass.
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export const FIREBASE_AUTH_ENABLED = !!firebaseConfig.apiKey;

// Guarded the same way ClerkProviders.tsx guarded ClerkProvider: a missing
// config degrades to "no auth" (console warning) rather than crashing a
// preview/PR build that hasn't had the env vars set yet.
export const firebaseApp = FIREBASE_AUTH_ENABLED
  ? getApps()[0] ?? initializeApp(firebaseConfig)
  : null;

export const auth = firebaseApp ? getAuth(firebaseApp) : null;
