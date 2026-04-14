import { useRef, useState, useEffect } from "react";
import { Outlet } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { Navbar } from "./Navbar";
import { Footer } from "./Footer";

const BACKGROUND_IMAGES = Array.from(
  { length: 17 },
  (_, index) => `/static/img/background_${index + 1}.avif`,
);

const FOCAL_POINTS = [
  "20% 20%",
  "50% 20%",
  "80% 20%",
  "20% 50%",
  "50% 50%",
  "80% 50%",
  "20% 80%",
  "50% 80%",
  "80% 80%",
];

const BACKGROUND_INTERVAL_MS = 5000;
const BACKGROUND_TRANSITION_MS = 3000;

type BackgroundSlide = {
  index: number;
  token: number;
  focalPoint: string;
};

function pickNextFocalPoint(previous: string) {
  const candidates = FOCAL_POINTS.filter((point) => point !== previous);
  return candidates[Math.floor(Math.random() * candidates.length)] ?? FOCAL_POINTS[4];
}

function createSlide(index: number, previousFocalPoint: string | null, token: number): BackgroundSlide {
  return {
    index,
    token,
    focalPoint: previousFocalPoint ? pickNextFocalPoint(previousFocalPoint) : FOCAL_POINTS[4],
  };
}

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
    <div className="relative min-h-screen overflow-x-hidden bg-white">
      <div className="app-shell relative mx-auto flex min-h-screen flex-col overflow-hidden">
        <BackgroundCarousel />

        <div className="relative z-[1] flex min-h-screen flex-col">
          <Navbar />

          <main className="relative z-[1] flex min-h-0 flex-1 items-center justify-center px-4 sm:px-6">
            <div className="w-full">
              <div ref={scrollRef} className="content-container">
                <div className="py-6">
                  <Outlet />
                </div>
              </div>

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
      </div>
    </div>
  );
}

function BackgroundCarousel() {
  const [currentSlide, setCurrentSlide] = useState<BackgroundSlide>(() => createSlide(0, null, 0));
  const [incomingSlide, setIncomingSlide] = useState<BackgroundSlide | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const currentSlideRef = useRef(currentSlide);
  const transitionLockedRef = useRef(false);

  useEffect(() => {
    BACKGROUND_IMAGES.slice(1).forEach((src) => {
      const image = new Image();
      image.src = src;
    });
  }, []);

  useEffect(() => {
    currentSlideRef.current = currentSlide;
  }, [currentSlide]);

  useEffect(() => {
    if (BACKGROUND_IMAGES.length < 2) {
      return;
    }

    const intervalId = window.setInterval(() => {
      if (transitionLockedRef.current) {
        return;
      }

      const nextIndex = (currentSlideRef.current.index + 1) % BACKGROUND_IMAGES.length;
      const nextSlide = createSlide(
        nextIndex,
        currentSlideRef.current.focalPoint,
        currentSlideRef.current.token + 1,
      );

      transitionLockedRef.current = true;
      setIncomingSlide(nextSlide);
    }, BACKGROUND_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    if (!incomingSlide) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      setIsTransitioning(true);
    });

    const timeoutId = window.setTimeout(() => {
      currentSlideRef.current = incomingSlide;
      setCurrentSlide(incomingSlide);
      setIncomingSlide(null);
      setIsTransitioning(false);
      transitionLockedRef.current = false;
    }, BACKGROUND_TRANSITION_MS);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.clearTimeout(timeoutId);
    };
  }, [incomingSlide]);

  return (
    <div className="app-shell-carousel" aria-hidden="true">
      <BackgroundLayer slide={currentSlide} visible fadingOut={Boolean(incomingSlide) && isTransitioning} />
      {incomingSlide ? <BackgroundLayer slide={incomingSlide} visible={isTransitioning} /> : null}
    </div>
  );
}

function BackgroundLayer({
  slide,
  visible,
  fadingOut = false,
}: {
  slide: BackgroundSlide;
  visible: boolean;
  fadingOut?: boolean;
}) {
  return (
    <div
      className={[
        "app-shell-slide",
        visible ? "is-visible" : "",
        fadingOut ? "is-fading-out" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <img
        key={`${slide.index}-${slide.token}`}
        src={BACKGROUND_IMAGES[slide.index]}
        alt=""
        className="app-shell-slide-image"
        style={{ transformOrigin: slide.focalPoint }}
        decoding="async"
        loading={slide.index === 0 ? "eager" : "lazy"}
      />
    </div>
  );
}
