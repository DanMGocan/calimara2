export function Footer() {
  return (
    <footer className="relative z-[1] border-t border-primary/8 px-4 py-4 text-center sm:px-6">
      <nav className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1" aria-label="Linkuri legale">
        <FooterLink href="/politica-de-confidentialitate">Confidențialitate</FooterLink>
        <Sep />
        <FooterLink href="/termeni-si-conditii">Termeni</FooterLink>
        <Sep />
        <FooterLink href="/politica-de-cookie-uri">Cookie-uri</FooterLink>
        <Sep />
        <FooterLink href="/contact">Contact</FooterLink>
        <Sep />
        <FooterLink href="/despre-noi">Despre</FooterLink>
        <Sep />
        <span className="text-[11px] text-primary/25">&copy; {new Date().getFullYear()} Calimara.ro</span>
      </nav>
    </footer>
  );
}

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} className="text-[11px] text-primary/40 transition-colors hover:text-primary/70 no-underline">
      {children}
    </a>
  );
}

function Sep() {
  return <span className="text-primary/15 select-none" aria-hidden="true">·</span>;
}
