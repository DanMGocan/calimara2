import { DebugLabel } from "@/components/ui/debug-label";

export function Footer() {
  return (
    <footer className="relative z-[1] border-t border-primary bg-white px-4 py-5 text-center sm:px-6">
      <DebugLabel name="Footer" />
      <nav className="relative flex flex-wrap items-center justify-center gap-x-4 gap-y-1" aria-label="Linkuri legale">
        <DebugLabel name="FooterNav" />
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
        <span className="text-xs text-muted-foreground">&copy; {new Date().getFullYear()} Calimara.ro</span>
      </nav>
    </footer>
  );
}

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} className="text-xs text-muted transition-colors hover:text-primary no-underline">
      {children}
    </a>
  );
}

function Sep() {
  return <span className="text-muted-foreground select-none" aria-hidden="true">·</span>;
}
