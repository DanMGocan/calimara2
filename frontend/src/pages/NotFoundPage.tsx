import { Helmet } from "react-helmet-async";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export default function NotFoundPage() {
  return (
    <>
      <Helmet>
        <title>404 - Pagina nu a fost gasita | Calimara</title>
      </Helmet>
      <div className="flex min-h-[60vh] flex-col items-center justify-center px-4">
        <h1 className="font-display text-6xl font-bold text-primary">404</h1>
        <p className="mt-4 text-lg text-muted">Pagina nu a fost gasita.</p>
        <Button asChild className="mt-8">
          <Link to="/">Inapoi acasa</Link>
        </Button>
      </div>
    </>
  );
}
