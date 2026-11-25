import { Link } from "react-router";

export default function NotFound() {
  return (
    <div className="max-w-md mx-auto px-4 py-24 text-center space-y-4">
      <h1 className="font-editorial text-4xl text-[var(--text-primary)]">Page not found</h1>
      <p className="text-sm text-[var(--text-secondary)]">That address doesn&rsquo;t exist in VivaIQ.</p>
      <Link to="/" className="inline-block text-sm font-semibold text-[var(--accent-primary)] hover:underline">
        Go to the home page →
      </Link>
    </div>
  );
}
