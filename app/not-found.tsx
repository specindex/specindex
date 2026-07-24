import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-24 text-center md:px-8">
      <h1 className="text-hero">Page not found</h1>
      <p className="mt-3 text-[var(--color-gray-600)]">That route is not in SpecIndex.</p>
      <Link href="/" className="btn btn-primary mt-8 inline-flex">
        Back home
      </Link>
    </div>
  );
}
