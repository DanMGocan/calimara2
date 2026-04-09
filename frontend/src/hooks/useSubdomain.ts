import { useMemo } from "react";
import { MAIN_DOMAIN, SUBDOMAIN_SUFFIX } from "@/lib/constants";

interface SubdomainInfo {
  isSubdomain: boolean;
  username: string | null;
}

export function useSubdomain(): SubdomainInfo {
  return useMemo(() => {
    const host = window.location.hostname;

    if (
      host.endsWith(SUBDOMAIN_SUFFIX) &&
      host !== MAIN_DOMAIN &&
      !host.startsWith("www.")
    ) {
      const username = host.replace(SUBDOMAIN_SUFFIX, "");
      return { isSubdomain: true, username };
    }

    return { isSubdomain: false, username: null };
  }, []);
}
