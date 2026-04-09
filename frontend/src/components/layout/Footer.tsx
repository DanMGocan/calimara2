export function Footer() {
  return (
    <footer className="border-t border-border bg-surface-raised py-8 mt-auto">
      <div className="mx-auto max-w-6xl px-4 text-center">
        <p className="font-display text-lg font-semibold text-primary">Calimara</p>
        <p className="mt-1 text-sm text-muted">
          Platforma de microblogging pentru scriitori si poeti &copy; {new Date().getFullYear()}
        </p>
      </div>
    </footer>
  );
}
