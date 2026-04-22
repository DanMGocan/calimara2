import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import {
  fetchFlaggedContent,
  fetchModerationLogs,
  fetchModerationQueue,
  fetchModerationStats,
  fetchPendingContent,
  moderateContent,
  reviewModerationLog,
  searchModerationUsers,
  suspendUser,
  unsuspendUser,
} from "@/api/moderation";
import type {
  ModerationItem,
  ModerationLog,
  ModerationQueueItem,
  ModerationUser,
} from "@/api/moderation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast-context";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { Stage, LeftCol } from "@/components/ui/stage";
import {
  ActionRow,
  ActionsGroup,
  SideKicker,
} from "@/components/ui/action-row";
import { formatDate } from "@/lib/utils";

type Tab = "overview" | "pending" | "flagged" | "queue" | "logs" | "users";

const TABS: { key: Tab; label: string; sub: string }[] = [
  { key: "overview", label: "Sumar", sub: "cifre generale" },
  { key: "pending", label: "În așteptare", sub: "de validat manual" },
  { key: "flagged", label: "Semnalate", sub: "raportate de utilizatori" },
  { key: "queue", label: "Coadă AI", sub: "analiză automată" },
  { key: "logs", label: "Jurnal", sub: "istoric moderare" },
  { key: "users", label: "Utilizatori", sub: "suspendare" },
];

export default function ModerationPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["moderation", "stats"],
    queryFn: fetchModerationStats,
  });
  const { data: pendingData } = useQuery({
    queryKey: ["moderation", "pending"],
    queryFn: fetchPendingContent,
    enabled: tab === "pending",
  });
  const { data: flaggedData } = useQuery({
    queryKey: ["moderation", "flagged"],
    queryFn: fetchFlaggedContent,
    enabled: tab === "flagged",
  });
  const { data: queueData } = useQuery({
    queryKey: ["moderation", "queue"],
    queryFn: fetchModerationQueue,
    enabled: tab === "queue",
  });
  const { data: logsData } = useQuery({
    queryKey: ["moderation", "logs"],
    queryFn: () => fetchModerationLogs(),
    enabled: tab === "logs",
  });

  const pending = pendingData?.content ?? [];
  const flagged = flaggedData?.content ?? [];
  const queue = queueData?.queue ?? [];
  const logs = logsData?.logs ?? [];

  const [actionModal, setActionModal] = useState<{
    type: string;
    id: number;
    isLog?: boolean;
  } | null>(null);
  const [actionChoice, setActionChoice] = useState("");
  const [actionReason, setActionReason] = useState("");

  const moderateMutation = useMutation({
    mutationFn: () => {
      if (actionModal?.isLog) {
        return reviewModerationLog(
          actionModal.id,
          actionChoice === "approve" ? "approved" : "rejected",
          actionReason,
        );
      }
      return moderateContent(
        actionModal!.type,
        actionModal!.id,
        actionChoice,
        actionReason,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["moderation"] });
      setActionModal(null);
      setActionChoice("");
      setActionReason("");
      showToast("Acțiune efectuată.", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const [userSearch, setUserSearch] = useState("");
  const [userData, setUserData] = useState<ModerationUser[]>([]);

  const handleUserSearch = async (q: string) => {
    setUserSearch(q);
    if (q.length >= 2) {
      const res = await searchModerationUsers(q);
      setUserData(res.users ?? []);
    } else {
      setUserData([]);
    }
  };

  const suspendMutation = useMutation({
    mutationFn: ({ userId, reason }: { userId: number; reason: string }) =>
      suspendUser(userId, reason),
    onSuccess: () => {
      showToast("Utilizator suspendat.", "success");
      handleUserSearch(userSearch);
    },
  });
  const unsuspendMutation = useMutation({
    mutationFn: (userId: number) => unsuspendUser(userId),
    onSuccess: () => {
      showToast("Suspendare ridicată.", "success");
      handleUserSearch(userSearch);
    },
  });

  if (statsLoading) return <PageLoader />;

  return (
    <>
      <Helmet>
        <title>Moderare | călimara.ro</title>
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>moderare</SideKicker>
            <ActionsGroup>
              {TABS.map((t, i) => (
                <ActionRow
                  key={t.key}
                  num={i + 1}
                  label={t.label}
                  sub={t.sub}
                  active={tab === t.key}
                  onClick={() => setTab(t.key)}
                />
              ))}
            </ActionsGroup>
          </aside>
        </LeftCol>

        <div className="piece-col">
          <div className="piece-wrap">
            {tab === "overview" && stats ? (
              <>
                <div className="piece-kind-row">
                  <span className="piece-kind-badge">sumar</span>
                  <span className="piece-kind-sep" />
                  <span className="piece-kind-meta">starea moderării</span>
                </div>
                <h1
                  className="piece-title"
                  style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 32 }}
                >
                  Sumar
                </h1>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: 16,
                  }}
                >
                  <StatTile label="În așteptare" value={stats.pending_count} />
                  <StatTile label="Semnalate" value={stats.flagged_count} />
                  <StatTile label="Suspendați" value={stats.suspended_count} />
                  <StatTile label="Acțiuni azi" value={stats.today_actions} />
                </div>
              </>
            ) : null}

            {(tab === "pending" || tab === "flagged") ? (
              <>
                <div className="piece-kind-row">
                  <span className="piece-kind-badge">
                    {tab === "pending" ? "în așteptare" : "semnalate"}
                  </span>
                  <span className="piece-kind-sep" />
                  <span className="piece-kind-meta">
                    {(tab === "pending" ? pending : flagged).length} elemente
                  </span>
                </div>
                <h1
                  className="piece-title"
                  style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 24 }}
                >
                  {tab === "pending" ? "De revizuit" : "Semnalate"}
                </h1>
                <ContentList
                  items={tab === "pending" ? pending : flagged}
                  onAction={(type, id, choice) => {
                    setActionModal({ type, id });
                    setActionChoice(choice);
                  }}
                />
              </>
            ) : null}

            {tab === "queue" ? (
              <>
                <div className="piece-kind-row">
                  <span className="piece-kind-badge">coadă ai</span>
                  <span className="piece-kind-sep" />
                  <span className="piece-kind-meta">{queue.length} elemente</span>
                </div>
                <h1
                  className="piece-title"
                  style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 24 }}
                >
                  Coada AI
                </h1>
                <QueueList
                  items={queue}
                  onAction={(type, logId, choice) => {
                    setActionModal({ type, id: logId, isLog: true });
                    setActionChoice(choice);
                  }}
                />
              </>
            ) : null}

            {tab === "logs" ? (
              <>
                <div className="piece-kind-row">
                  <span className="piece-kind-badge">jurnal</span>
                  <span className="piece-kind-sep" />
                  <span className="piece-kind-meta">{logs.length} intrări</span>
                </div>
                <h1
                  className="piece-title"
                  style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 24 }}
                >
                  Jurnal de moderare
                </h1>
                <LogsList logs={logs} />
              </>
            ) : null}

            {tab === "users" ? (
              <>
                <div className="piece-kind-row">
                  <span className="piece-kind-badge">utilizatori</span>
                  <span className="piece-kind-sep" />
                  <span className="piece-kind-meta">{userData.length} rezultate</span>
                </div>
                <h1
                  className="piece-title"
                  style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 24 }}
                >
                  Utilizatori
                </h1>
                <Input
                  placeholder="caută utilizator…"
                  value={userSearch}
                  onChange={(e) => handleUserSearch(e.target.value)}
                  style={{ maxWidth: 420, marginBottom: 20 }}
                />
                <div className="flex flex-col gap-2">
                  {userData.map((u) => (
                    <div
                      key={u.id}
                      className="flex items-center justify-between"
                      style={{
                        padding: "12px 16px",
                        border: "1px solid var(--color-hairline)",
                        borderRadius: 10,
                        background: "rgba(255,255,255,0.6)",
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <span
                          style={{
                            fontFamily: "var(--font-sans)",
                            fontSize: 14,
                            fontWeight: 600,
                            color: "var(--color-ink)",
                          }}
                        >
                          {u.username}
                        </span>
                        {u.is_suspended ? (
                          <Badge variant="danger">Suspendat</Badge>
                        ) : null}
                      </div>
                      {u.is_suspended ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => unsuspendMutation.mutate(u.id)}
                        >
                          ridică suspendarea
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => {
                            const reason = window.prompt("Motivul suspendării:");
                            if (reason) suspendMutation.mutate({ userId: u.id, reason });
                          }}
                        >
                          suspendă
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </div>
        </div>
      </Stage>

      <Dialog open={actionModal !== null} onOpenChange={() => setActionModal(null)}>
        <DialogContent>
          <DialogHeader>
            <div className="auth-kicker">moderare</div>
            <DialogTitle>
              {actionChoice === "approve" ? "Aprobă" : "Respinge"} conținutul
            </DialogTitle>
          </DialogHeader>
          <Input
            placeholder="motiv (opțional)"
            value={actionReason}
            onChange={(e) => setActionReason(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setActionModal(null)}>
              anulează
            </Button>
            <Button
              variant={actionChoice === "approve" ? "default" : "danger"}
              onClick={() => moderateMutation.mutate()}
              disabled={moderateMutation.isPending}
            >
              {actionChoice === "approve" ? "aprobă" : "respinge"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rail-stat" style={{ borderBottom: "none" }}>
      <span className="rail-label">{label}</span>
      <span className="rail-count">{value}</span>
    </div>
  );
}

function ContentList({
  items,
  onAction,
}: {
  items: ModerationItem[];
  onAction: (type: string, id: number, choice: string) => void;
}) {
  if (items.length === 0) {
    return (
      <div
        style={{
          padding: "60px 20px",
          border: "1px dashed var(--color-hairline-strong)",
          borderRadius: 10,
          textAlign: "center",
          color: "var(--color-ink-faint)",
          fontFamily: "var(--font-serif)",
          fontStyle: "italic",
          fontSize: 17,
        }}
      >
        Nimic de revizuit.
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <div
          key={`${item.type}-${item.id}`}
          style={{
            padding: "16px 18px",
            border: "1px solid var(--color-hairline)",
            borderRadius: 10,
            background: "rgba(255,255,255,0.6)",
          }}
        >
          <div className="flex items-start justify-between gap-4">
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="outline">{item.type}</Badge>
                <span
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--color-ink)",
                  }}
                >
                  {item.author}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    letterSpacing: "0.08em",
                    color: "var(--color-ink-faint)",
                  }}
                >
                  {formatDate(item.created_at)}
                </span>
              </div>
              {item.title ? (
                <p
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontSize: 17,
                    fontWeight: 500,
                    color: "var(--color-ink)",
                    letterSpacing: "-0.01em",
                    margin: "8px 0 4px",
                  }}
                >
                  {item.title}
                </p>
              ) : null}
              <p
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 14,
                  color: "var(--color-ink-mute)",
                  margin: 0,
                  lineHeight: 1.5,
                  display: "-webkit-box",
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {item.content}
              </p>
              {item.toxicity_score > 0 ? (
                <div style={{ marginTop: 10 }}>
                  <Badge
                    variant={
                      item.toxicity_score > 0.5
                        ? "danger"
                        : item.toxicity_score > 0.2
                          ? "warning"
                          : "success"
                    }
                  >
                    Toxicitate: {(item.toxicity_score * 100).toFixed(0)}%
                  </Badge>
                </div>
              ) : null}
            </div>
            <div className="flex flex-col gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => onAction(item.type, item.id, "approve")}
              >
                aprobă
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => onAction(item.type, item.id, "reject")}
              >
                respinge
              </Button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function QueueList({
  items,
  onAction,
}: {
  items: ModerationQueueItem[];
  onAction: (type: string, logId: number, choice: string) => void;
}) {
  if (items.length === 0) {
    return (
      <div
        style={{
          padding: "60px 20px",
          border: "1px dashed var(--color-hairline-strong)",
          borderRadius: 10,
          textAlign: "center",
          color: "var(--color-ink-faint)",
          fontFamily: "var(--font-serif)",
          fontStyle: "italic",
          fontSize: 17,
        }}
      >
        Nimic în coadă.
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <div
          key={`log-${item.log_id}`}
          style={{
            padding: "16px 18px",
            border: "1px solid var(--color-hairline)",
            borderRadius: 10,
            background: "rgba(255,255,255,0.6)",
          }}
        >
          <div className="flex items-start justify-between gap-4">
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="outline">{item.content_type}</Badge>
                <span
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--color-ink)",
                  }}
                >
                  {item.content.author}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    letterSpacing: "0.08em",
                    color: "var(--color-ink-faint)",
                  }}
                >
                  {formatDate(item.flagged_at)}
                </span>
              </div>
              {item.content.title ? (
                <p
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontSize: 17,
                    fontWeight: 500,
                    color: "var(--color-ink)",
                    letterSpacing: "-0.01em",
                    margin: "8px 0 4px",
                  }}
                >
                  {item.content.title}
                </p>
              ) : null}
              <p
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 14,
                  color: "var(--color-ink-mute)",
                  margin: 0,
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.5,
                }}
              >
                {item.content.content}
              </p>
              <div
                style={{
                  marginTop: 14,
                  padding: 12,
                  border: "1px solid var(--color-hairline)",
                  borderRadius: 8,
                  background: "var(--color-paper-2)",
                }}
              >
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "var(--color-accent)",
                    marginBottom: 6,
                  }}
                >
                  analiză ai · {item.ai_analysis.decision}
                </div>
                <p
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontStyle: "italic",
                    fontSize: 13,
                    color: "var(--color-ink-mute)",
                    margin: "0 0 8px",
                  }}
                >
                  "{item.ai_analysis.reason}"
                </p>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="danger">
                    Toxicitate: {(item.ai_analysis.toxicity_score * 100).toFixed(0)}%
                  </Badge>
                  {(item.ai_analysis.hate_speech_score ?? 0) > 0.1 ? (
                    <Badge variant="danger">
                      Discurs ură: {((item.ai_analysis.hate_speech_score ?? 0) * 100).toFixed(0)}%
                    </Badge>
                  ) : null}
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => onAction(item.content_type, item.log_id, "approve")}
              >
                aprobă
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => onAction(item.content_type, item.log_id, "reject")}
              >
                respinge
              </Button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function LogsList({ logs }: { logs: ModerationLog[] }) {
  if (logs.length === 0) {
    return (
      <p
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: 13,
          color: "var(--color-ink-faint)",
        }}
      >
        Nicio intrare.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {logs.map((log) => (
        <div
          key={log.id}
          style={{
            padding: "12px 16px",
            border: "1px solid var(--color-hairline)",
            borderRadius: 10,
            background: "rgba(255,255,255,0.6)",
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            color: "var(--color-ink-soft)",
          }}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline">{log.content_type}</Badge>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.08em",
                color: "var(--color-ink-faint)",
              }}
            >
              {formatDate(log.created_at)}
            </span>
            <Badge variant={log.ai_decision === "approved" ? "success" : "warning"}>
              {log.ai_decision}
            </Badge>
            {log.toxicity_score > 0 ? (
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color: "var(--color-ink-faint)",
                }}
              >
                tox {(log.toxicity_score * 100).toFixed(0)}%
              </span>
            ) : null}
          </div>
          <p style={{ margin: "6px 0 0", color: "var(--color-ink-mute)" }}>
            {log.ai_reason}
          </p>
          {log.human_decision ? (
            <p
              style={{
                marginTop: 6,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              decizie umană:{" "}
              <Badge variant={log.human_decision === "approved" ? "success" : "danger"}>
                {log.human_decision}
              </Badge>
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}
