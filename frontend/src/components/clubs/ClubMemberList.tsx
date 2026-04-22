import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  kickClubMember,
  updateClubMemberRole,
  type ClubMember,
  type ClubMemberRole,
} from "@/api/clubs";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/hooks/useAuth";
import { getAvatarUrl, formatDate, getBlogUrl } from "@/lib/utils";

interface Props {
  clubId: number;
  clubSlug: string;
  ownerId: number;
  members: ClubMember[];
  myRole: ClubMemberRole | null;
}

const ROLE_LABEL: Record<ClubMemberRole, string> = {
  owner: "Proprietar",
  admin: "Administrator",
  member: "Membru",
};

export function ClubMemberList({ clubId, clubSlug, ownerId, members, myRole }: Props) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const qc = useQueryClient();
  const [busyId, setBusyId] = useState<number | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["clubs", "bySlug", clubSlug] });

  const kick = useMutation({
    mutationFn: (userId: number) => kickClubMember(clubId, userId),
    onMutate: (userId) => setBusyId(userId),
    onSuccess: () => {
      showToast("Membru scos din club", "success");
      invalidate();
    },
    onError: (e: Error) => showToast(e.message || "Acțiune eșuată", "danger"),
    onSettled: () => setBusyId(null),
  });

  const changeRole = useMutation({
    mutationFn: (vars: { userId: number; role: "admin" | "member" }) =>
      updateClubMemberRole(clubId, vars.userId, vars.role),
    onMutate: (vars) => setBusyId(vars.userId),
    onSuccess: () => {
      showToast("Rol actualizat", "success");
      invalidate();
    },
    onError: (e: Error) => showToast(e.message || "Acțiune eșuată", "danger"),
    onSettled: () => setBusyId(null),
  });

  const isOwner = myRole === "owner";
  const isAdmin = myRole === "admin";

  const canKick = (m: ClubMember) => {
    if (!user) return false;
    if (m.user_id === user.id) return m.role !== "owner"; // user can leave (unless owner)
    if (isOwner) return m.role !== "owner";
    if (isAdmin) return m.role === "member";
    return false;
  };

  return (
    <div>
      <h2
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          letterSpacing: "0.22em",
          textTransform: "uppercase",
          color: "var(--color-ink-mute)",
          margin: "24px 0 8px",
        }}
      >
        Membri ({members.length})
      </h2>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {members.map((m) => {
          const seed = m.avatar_seed || `${m.username}-shapes`;
          const isMe = user && m.user_id === user.id;
          return (
            <li
              key={m.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 0",
                borderBottom: "1px solid var(--color-hairline)",
              }}
            >
              <img
                src={getAvatarUrl(seed, 36)}
                width={36}
                height={36}
                alt=""
                style={{
                  borderRadius: 4,
                  flexShrink: 0,
                  background: "var(--color-paper-2)",
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <a
                  href={getBlogUrl(m.username)}
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontSize: 16,
                    color: "var(--color-ink)",
                    textDecoration: "none",
                  }}
                >
                  {m.username}
                </a>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "var(--color-ink-faint)",
                    marginTop: 2,
                    display: "flex",
                    gap: 12,
                    flexWrap: "wrap",
                  }}
                >
                  <span>{ROLE_LABEL[m.role]}</span>
                  <span>din {formatDate(m.joined_at)}</span>
                  <span>
                    {m.contribution_count}{" "}
                    {m.contribution_count === 1 ? "contribuție" : "contribuții"}
                  </span>
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                {isOwner && m.user_id !== ownerId && m.role === "member" ? (
                  <button
                    type="button"
                    className="cal-btn"
                    disabled={busyId === m.user_id}
                    onClick={() =>
                      changeRole.mutate({ userId: m.user_id, role: "admin" })
                    }
                  >
                    Promovează
                  </button>
                ) : null}
                {isOwner && m.user_id !== ownerId && m.role === "admin" ? (
                  <button
                    type="button"
                    className="cal-btn"
                    disabled={busyId === m.user_id}
                    onClick={() =>
                      changeRole.mutate({ userId: m.user_id, role: "member" })
                    }
                  >
                    Demotează
                  </button>
                ) : null}
                {canKick(m) ? (
                  <button
                    type="button"
                    className="cal-btn"
                    disabled={busyId === m.user_id}
                    onClick={() => {
                      const msg = isMe
                        ? "Sigur vrei să părăsești clubul?"
                        : `Scoți pe ${m.username} din club?`;
                      if (confirm(msg)) kick.mutate(m.user_id);
                    }}
                  >
                    {isMe ? "Părăsește" : "Scoate"}
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
