export function Footer() {
  return (
    <footer className="relative z-[1] border-t border-primary/10 bg-beige-light py-10 text-center">
      <div className="mx-auto max-w-6xl px-4">
        <p className="font-display text-2xl font-medium text-primary">Calimara.ro</p>
        <p className="mt-1 text-sm text-muted">
          Platformă românească de microblogging pentru scriitori și poeți
        </p>

        <nav className="mt-6 flex flex-wrap justify-center gap-x-6 gap-y-2" aria-label="Linkuri legale">
          <FooterLink href="/politica-de-confidentialitate">Politica de Confidențialitate</FooterLink>
          <FooterLink href="/termeni-si-conditii">Termeni și Condiții</FooterLink>
          <FooterLink href="/politica-de-cookie-uri">Politica de Cookie-uri</FooterLink>
          <FooterLink href="/contact">Contact</FooterLink>
          <FooterLink href="/despre-noi">Despre Noi</FooterLink>
        </nav>

        <p className="mt-6 text-xs text-primary/30">
          &copy; {new Date().getFullYear()} Calimara.ro. Toate drepturile rezervate.
        </p>
      </div>
    </footer>
  );
}

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      className="text-sm text-primary/60 transition-colors hover:text-primary no-underline"
    >
      {children}
    </a>
  );
}
