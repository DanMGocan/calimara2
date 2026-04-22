import { forwardRef } from "react";
import type { AnchorHTMLAttributes } from "react";
import { Link } from "react-router-dom";
import { resolveSameOrigin } from "@/lib/utils";

type SmartLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  href: string;
};

export const SmartLink = forwardRef<HTMLAnchorElement, SmartLinkProps>(
  function SmartLink({ href, children, ...rest }, ref) {
    const internal = resolveSameOrigin(href);
    if (internal !== null) {
      return (
        <Link ref={ref} to={internal} {...rest}>
          {children}
        </Link>
      );
    }
    return (
      <a ref={ref} href={href} {...rest}>
        {children}
      </a>
    );
  },
);
