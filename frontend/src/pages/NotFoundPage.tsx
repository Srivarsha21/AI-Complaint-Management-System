import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <p className="text-sm font-semibold text-brand-600">404</p>
      <h1 className="mt-2 text-2xl font-bold">Page not found</h1>
      <p className="mt-2 text-slate-500">The page you are looking for does not exist.</p>
      <Link to="/" className="mt-6 inline-block text-sm font-medium text-brand-600 hover:underline">
        Go back home
      </Link>
    </div>
  );
}
