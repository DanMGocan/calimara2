import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchClubRequests, respondClubRequest, type ClubJoinRequest } from "@/api/clubs";
import { useToast } from "@/components/ui/toast-context";
import { formatRelativeTime, getAvatarUrl, getBlogUrl } from "@/lib/utils";

interface Props {
  clubId: number;
  clubSlug: string;
}

export function ManageClubRequestsSection({ clubId, clubSlug }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["clubs", clubId, "requests"],
    queryFn: () => fetchClubRequests(clubId),
  });
  const { showToast } = useToast();
  const qc = useQueryClient();

  const respond = useMutation({
    mutationFn: (vars: { requestId: number; action: "approve" | "reject" }) =>
      respondClubRequest(clubId, vars.requestId, vars.action),
    onSuccess: (_, vars) => {
      showToast(
        vars.action === "approve" ? "Cerere acceptată" : "Cerere respinsă",
        "success",
      );
      qc.invalidateQueries({ queryKey: ["clubs", clubId, "requests"] });
      qc.invalidateQueries({ queryKey: ["clubs", "bySlug", clubSlug] });
    },
    onError: (e: Error) => showToast(e.message || "Acțiune eșuată", "danger"),
  });

  if (isLoading) return null;
  const requests = data?.requests ?? [];
  if (requests.length === 0) return null;

  const applications = requests.filter((r) => r.direction === "application");
  const invitations = requests.filter((r) => r.direction === "invitation");

  const renderRow = (req: ClubJoinRequest) => {
    const seed = req.user?.avatar_seed || `${req.user?.username ?? "anon"}-shapes`;
    return (
      <li
        key={req.id}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "8px 0",
          borderBottom: "1px solid var(--color-hairline)",
        }}
      >
        <img
          src={getAvatarUrl(seed, 28)}
          width={28}
          height={28}
          alt=""
          style={{ borderRadius: 4, background: "var(--color-paper-2)" }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <a
            href={req.user ? getBlogUrl(req.user.username) : "#"}
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 14,
              color: "var(--color-ink)",
              textDecoration: "none",
            }}
          >
            {req.user?.username ?? "necunoscut"}
          </a>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: "0.18em",
              color: "var(--color-ink-faint)",
              marginLeft: 10,
            }}
          >
            {formatRelativeTime(req.created_at)}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {req.direction === "application" ? (
            <>
              <button
                type="button"
                className="cal-btn"
                disabled={respond.isPending}
                onClick={() => respond.mutate({ requestId: req.id, action: "approve" })}
              >
                Acceptă
              </button>
              <button
                type="button"
                className="cal-btn"
                disabled={respond.isPending}
                onClick={() => respond.mutate({ requestId: req.id, action: "reject" })}
              >
                Refuză
              </button>
            </>
          ) : (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.18em",
                color: "var(--color-ink-faint)",
              }}
            >
              invitat — așteaptă răspuns
            </span>
          )}
        </div>
      </li>
    );
  };

  return (
    <div
      style={{
        border: "1px solid var(--color-hairline)",
        borderRadius: 8,
        padding: 14,
        margin: "16px 0",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          letterSpacing: "0.22em",
          textTransform: "uppercase",
          color: "var(--color-ink-mute)",
          marginBottom: 6,
        }}
      >
        Cereri în așteptare ({requests.length})
      </div>
      {applications.length > 0 ? (
        <>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: "0.18em",
              color: "var(--color-ink-faint)",
              marginTop: 4,
            }}
          >
            Cereri de aderare
          </div>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {applications.map(renderRow)}
          </ul>
        </>
      ) : null}
      {invitations.length > 0 ? (
        <>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: "0.18em",
              color: "var(--color-ink-faint)",
              marginTop: 8,
            }}
          >
            Invitații trimise
          </div>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {invitations.map(renderRow)}
          </ul>
        </>
      ) : null}
    </div>
  );
}
