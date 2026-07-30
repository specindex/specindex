"use client";

// Small client-component wrapper so plain Server Component marketing pages
// (app/about, app/how-it-works, app/reporting, etc.) can drop in a working
// "Request Demo" trigger without becoming client components themselves --
// only this button needs useDemoModal().
import { useDemoModal } from "@/components/marketing/DemoModal";

export function RequestDemoButton({
  className,
  children = "Request Demo",
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  const { openDemoModal } = useDemoModal();
  return (
    <button type="button" onClick={() => openDemoModal()} className={className}>
      {children}
    </button>
  );
}
