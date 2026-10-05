import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ElementType,
  type ReactNode,
} from "react";
import "./anim.css";

export default function Reveal({
  children,
  delay = 0,
  as: Tag = "div",
  className,
  rise = 24,
  role,
}: {
  children: ReactNode;
  delay?: number;
  as?: ElementType;
  className?: string;
  rise?: number;
  role?: string;
}) {
  const ref = useRef<HTMLElement | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (el.getBoundingClientRect().top < window.innerHeight) {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[entries.length - 1]?.isIntersecting) {
          setInView(true);
          io.disconnect();
        }
      },
      { threshold: 0.1, rootMargin: "0px 0px -5% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <Tag
      ref={ref}
      data-reveal=""
      role={role}
      className={`${inView ? "is-in" : ""} ${className ?? ""}`}
      style={{ "--reveal-delay": `${delay}ms`, "--reveal-rise": `${rise}px` } as CSSProperties}
    >
      {children}
    </Tag>
  );
}
