import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { Shield, AlertTriangle, Clock, FileText, Users, BarChart3, CheckCircle, XCircle } from "lucide-react";
import { fetchModerationStats, fetchPendingContent, fetchFlaggedContent, fetchModerationQueue, fetchModerationLogs, moderateContent, reviewModerationLog, searchModerationUsers, suspendUser, unsuspendUser } from "@/api/moderation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { formatDate } from "@/lib/utils";

type Tab = "overview" | "pending" | "flagged" | "queue" | "logs" | "users";

export default function ModerationPage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["moderation", "stats"],
    queryFn: fetchModerationStats,
  });

  const { data: pending } = useQuery({
    queryKey: ["moderation", "pending"],
    queryFn: fetchPendingContent,
    enabled: activeTab === "pending",
  });

  const { data: flagged } = useQuery({
    queryKey: ["moderation", "flagged"],
    queryFn: fetchFlaggedContent,
    enabled: activeTab === "flagged",
  });

  const { data: queue } = useQuery({
    queryKey: ["moderation", "queue"],
    queryFn: fetchModerationQueue,
    enabled: activeTab === "queue",
  });

  const { data: logs } = useQuery({
    queryKey: ["moderation", "logs"],
    queryFn: () => fetchModerationLogs(),
    enabled: activeTab === "logs",
  });

  // Moderate action
  const [actionModal, setActionModal] = useState<{ type: string; id: number } | null>(null);
  const [actionChoice, setActionChoice] = useState("");
  const [actionReason, setActionReason] = useState("");

  const moderateMutation = useMutation({
    mutationFn: () => moderateContent(actionModal!.type, actionModal!.id, actionChoice, actionReason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["moderation"] });
      setActionModal(null);
      setActionChoice("");
      setActionReason("");
      showToast("Actiune efectuata!", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  // User management
  const [userSearch, setUserSearch] = useState("");
  const [userResults, setUserResults] = useState<{ id: number; username: string; is_suspended: boolean }[]>([]);

  const handleUserSearch = async (q: string) => {
    setUserSearch(q);
    if (q.length >= 2) {
      const results = await searchModerationUsers(q);
      setUserResults(results);
    } else {
      setUserResults([]);
    }
  };

  const suspendMutation = useMutation({
    mutationFn: ({ userId, reason }: { userId: number; reason: string }) => suspendUser(userId, reason),
    onSuccess: () => { showToast("Utilizator suspendat!", "success"); handleUserSearch(userSearch); },
  });

  const unsuspendMutation = useMutation({
    mutationFn: (userId: number) => unsuspendUser(userId),
    onSuccess: () => { showToast("Suspendare ridicata!", "success"); handleUserSearch(userSearch); },
  });

  if (statsLoading) return <PageLoader />;

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: "Sumar", icon: <BarChart3 className="h-4 w-4" /> },
    { key: "pending", label: "In asteptare", icon: <Clock className="h-4 w-4" /> },
    { key: "flagged", label: "Semnalate", icon: <AlertTriangle className="h-4 w-4" /> },
    { key: "queue", label: "Coada AI", icon: <Shield className="h-4 w-4" /> },
    { key: "logs", label: "Jurnal", icon: <FileText className="h-4 w-4" /> },
    { key: "users", label: "Utilizatori", icon: <Users className="h-4 w-4" /> },
  ];

  return (
    <>
      <Helmet>
        <title>Moderare | Calimara</title>
      </Helmet>

      <div className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="font-display text-2xl font-bold text-primary mb-6 flex items-center gap-2">
          <Shield className="h-6 w-6 text-accent" /> Panou de moderare
        </h1>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border mb-6 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer whitespace-nowrap ${
                activeTab === tab.key
                  ? "border-accent text-accent"
                  : "border-transparent text-muted hover:text-primary"
              }`}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        {/* Overview */}
        {activeTab === "overview" && stats && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="In asteptare" value={stats.pending_count} icon={<Clock className="h-5 w-5 text-warning" />} />
            <StatCard label="Semnalate" value={stats.flagged_count} icon={<AlertTriangle className="h-5 w-5 text-danger" />} />
            <StatCard label="Suspendati" value={stats.suspended_count} icon={<Users className="h-5 w-5 text-muted" />} />
            <StatCard label="Actiuni azi" value={stats.today_actions} icon={<CheckCircle className="h-5 w-5 text-success" />} />
          </div>
        )}

        {/* Pending / Flagged / Queue content */}
        {(activeTab === "pending" || activeTab === "flagged" || activeTab === "queue") && (
          <div className="space-y-3">
            {(activeTab === "pending" ? pending : activeTab === "flagged" ? flagged : queue)?.map((item) => (
              <Card key={`${item.content_type}-${item.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant={item.content_type === "post" ? "default" : "secondary"}>{item.content_type}</Badge>
                        <span className="text-sm font-medium text-primary">{item.author}</span>
                        <span className="text-xs text-muted">{formatDate(item.created_at)}</span>
                      </div>
                      {item.title && <p className="mt-1 font-medium text-primary">{item.title}</p>}
                      <p className="mt-1 text-sm text-muted line-clamp-3">{item.content}</p>
                      {item.toxicity_score > 0 && (
                        <div className="mt-2">
                          <Badge variant={item.toxicity_score > 0.5 ? "danger" : item.toxicity_score > 0.2 ? "warning" : "success"}>
                            Toxicitate: {(item.toxicity_score * 100).toFixed(0)}%
                          </Badge>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-1 ml-4">
                      <Button size="sm" variant="outline" onClick={() => { setActionModal({ type: item.content_type, id: item.content_id }); setActionChoice("approve"); }}>
                        <CheckCircle className="h-3.5 w-3.5 text-success" />
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => { setActionModal({ type: item.content_type, id: item.content_id }); setActionChoice("reject"); }}>
                        <XCircle className="h-3.5 w-3.5 text-danger" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {(activeTab === "pending" ? pending : activeTab === "flagged" ? flagged : queue)?.length === 0 && (
              <div className="rounded-xl border border-border bg-surface-raised p-12 text-center">
                <p className="text-muted">Nimic de revizuit.</p>
              </div>
            )}
          </div>
        )}

        {/* Logs */}
        {activeTab === "logs" && (
          <div className="space-y-3">
            {logs?.logs.map((log) => (
              <Card key={log.id}>
                <CardContent className="p-4 text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={log.content_type === "post" ? "default" : "secondary"}>{log.content_type}</Badge>
                    <span className="text-muted">{formatDate(log.created_at)}</span>
                    <Badge variant={log.ai_decision === "approved" ? "success" : "warning"}>{log.ai_decision}</Badge>
                    {log.toxicity_score > 0 && (
                      <span className="text-xs text-muted">Toxicitate: {(log.toxicity_score * 100).toFixed(0)}%</span>
                    )}
                  </div>
                  <p className="text-muted">{log.ai_reason}</p>
                  {log.human_decision && (
                    <p className="mt-1 text-primary">Decizie umana: <Badge variant={log.human_decision === "approved" ? "success" : "danger"}>{log.human_decision}</Badge></p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Users */}
        {activeTab === "users" && (
          <div>
            <Input
              placeholder="Cauta utilizator..."
              value={userSearch}
              onChange={(e) => handleUserSearch(e.target.value)}
              className="mb-4 max-w-md"
            />
            <div className="space-y-2">
              {userResults.map((u) => (
                <div key={u.id} className="flex items-center justify-between rounded-lg border border-border bg-surface-raised p-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-primary">{u.username}</span>
                    {u.is_suspended && <Badge variant="danger">Suspendat</Badge>}
                  </div>
                  {u.is_suspended ? (
                    <Button size="sm" variant="outline" onClick={() => unsuspendMutation.mutate(u.id)}>Ridica suspendarea</Button>
                  ) : (
                    <Button size="sm" variant="danger" onClick={() => {
                      const reason = window.prompt("Motivul suspendarii:");
                      if (reason) suspendMutation.mutate({ userId: u.id, reason });
                    }}>Suspenda</Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Action Modal */}
      <Dialog open={actionModal !== null} onOpenChange={() => setActionModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{actionChoice === "approve" ? "Aproba" : "Respinge"} continutul</DialogTitle>
          </DialogHeader>
          <Input
            placeholder="Motiv (optional)"
            value={actionReason}
            onChange={(e) => setActionReason(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setActionModal(null)}>Anuleaza</Button>
            <Button
              variant={actionChoice === "approve" ? "default" : "danger"}
              onClick={() => moderateMutation.mutate()}
              disabled={moderateMutation.isPending}
            >
              {actionChoice === "approve" ? "Aproba" : "Respinge"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function StatCard({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        {icon}
        <div>
          <p className="text-2xl font-bold text-primary">{value}</p>
          <p className="text-sm text-muted">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}
