export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="site-foot">
      <div className="foot-inner">
        <nav className="foot-links" aria-label="Linkuri legale">
          <a href="/politica-de-confidentialitate">Politica de confidențialitate</a>
          <a href="/termeni-si-conditii">Termeni și condiții</a>
          <a href="/contact">Contact</a>
        </nav>
        <div className="foot-mark">© {year} călimara.ro</div>
        <div className="foot-social">
          <a href="#" className="social-btn" aria-label="Facebook">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M13.5 21v-7.5h2.5l.4-3h-2.9V8.6c0-.9.3-1.5 1.5-1.5H16.5V4.4c-.3 0-1.2-.1-2.2-.1-2.2 0-3.7 1.3-3.7 3.8V10.5H8v3h2.6V21h2.9z" />
            </svg>
          </a>
          <a href="#" className="social-btn" aria-label="X">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M17.5 3h3.2l-7 8 8.2 10h-6.4l-5-6.5L4.8 21H1.6l7.5-8.6L1.2 3h6.6l4.5 6 5.2-6zm-1.1 16.2h1.8L7.7 4.7H5.8l10.6 14.5z" />
            </svg>
          </a>
        </div>
      </div>
    </footer>
  );
}
