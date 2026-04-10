import { useRef, useState, useEffect } from "react";
import { Outlet } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { Navbar } from "./Navbar";
import { Footer } from "./Footer";

export function Layout() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showArrow, setShowArrow] = useState(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const check = () => {
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
      const noOverflow = el.scrollHeight <= el.clientHeight;
      setShowArrow(!atBottom && !noOverflow);
    };

    check();
    el.addEventListener("scroll", check);
    // Re-check when content changes
    const observer = new ResizeObserver(check);
    observer.observe(el);

    return () => {
      el.removeEventListener("scroll", check);
      observer.disconnect();
    };
  }, []);

  return (
    <div className="relative flex min-h-screen flex-col">
      {/* Atmospheric top image */}
      <div className="top-page-image" aria-hidden="true" />

      <Navbar />

      <main className="relative z-[1] flex flex-1 items-center justify-center px-4">
        <div className="w-full max-w-2xl">
          <div ref={scrollRef} className="content-container">
            <div className="px-4 py-6 sm:px-8">
              <Outlet />
            </div>
          </div>

          {/* Scroll indicator arrow */}
          <div
            className="py-3 text-center text-accent transition-opacity duration-300"
            style={{
              opacity: showArrow ? 1 : 0,
              animation: showArrow ? "bounceDown 2s ease-in-out infinite" : "none",
            }}
            aria-hidden="true"
          >
            <ChevronDown className="mx-auto h-6 w-6" />
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
