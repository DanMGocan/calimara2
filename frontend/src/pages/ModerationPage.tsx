import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { Shield, AlertTriangle, Clock, FileText, Users, BarChart3, CheckCircle, XCircle } from "lucide-react";
import { 
  fetchModerationStats, 
  fetchPendingContent, 
  fetchFlaggedContent, 
  fetchModerationQueue, 
  fetchModerationLogs, 
  moderateContent, 
  reviewModerationLog, 
  searchModerationUsers, 
  suspendUser, 
  unsuspendUser,
} from "@/api/moderation";
import type {
  ModerationItem,
  ModerationQueueItem,
  ModerationLog,
  ModerationUser
} from "@/api/moderation";
import { Card, CardContent } from "@/components/ui/card";
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

  const { data: pendingData } = useQuery({
    queryKey: ["moderation", "pending"],
    queryFn: fetchPendingContent,
    enabled: activeTab === "pending",
  });
  const pending = pendingData?.content || [];

  const { data: flaggedData } = useQuery({
    queryKey: ["moderation", "flagged"],
    queryFn: fetchFlaggedContent,
    enabled: activeTab === "flagged",
  });
  const flagged = flaggedData?.content || [];

  const { data: queueData } = useQuery({
    queryKey: ["moderation", "queue"],
    queryFn: fetchModerationQueue,
    enabled: activeTab === "queue",
  });
  const queue = queueData?.queue || [];

  const { data: logsData } = useQuery({
    queryKey: ["moderation", "logs"],
    queryFn: () => fetchModerationLogs(),
    enabled: activeTab === "logs",
  });
  const logs = logsData?.logs || [];

  // Moderate action
  const [actionModal, setActionModal] = useState<{ type: string; id: number; isLog?: boolean } | null>(null);
  const [actionChoice, setActionChoice] = useState("");
  const [actionReason, setActionReason] = useState("");

  const moderateMutation = useMutation({
    mutationFn: () => {
      if (actionModal?.isLog) {
        return reviewModerationLog(actionModal.id, actionChoice === "approve" ? "approved" : "rejected", actionReason);
      }
      return moderateContent(actionModal!.type, actionModal!.id, actionChoice, actionReason);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["moderation"] });
      setActionModal(null);
      setActionChoice("");
      setActionReason("");
      showToast("Acțiune efectuată!", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  // User management
  const [userSearch, setUserSearch] = useState("");
  const [userData, setUserData] = useState<ModerationUser[]>([]);

  const handleUserSearch = async (q: string) => {
    setUserSearch(q);
    if (q.length >= 2) {
      const results = await searchModerationUsers(q);
      setUserData(results.users || []);
    } else {
      setUserData([]);
    }
  };

  const suspendMutation = useMutation({
    mutationFn: ({ userId, reason }: { userId: number; reason: string }) => suspendUser(userId, reason),
    onSuccess: () => { showToast("Utilizator suspendat!", "success"); handleUserSearch(userSearch); },
  });

  const unsuspendMutation = useMutation({
    mutationFn: (userId: number) => unsuspendUser(userId),
    onSuccess: () => { showToast("Suspendare ridicată!", "success"); handleUserSearch(userSearch); },
  });

  if (statsLoading) return <PageLoader />;

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: "Sumar", icon: <BarChart3 className="h-4 w-4" /> },
    { key: "pending", label: "În așteptare", icon: <Clock className="h-4 w-4" /> },
    { key: "flagged", label: "Semnalate", icon: <AlertTriangle className="h-4 w-4" /> },
    { key: "queue", label: "Coada AI", icon: <Shield className="h-4 w-4" /> },
    { key: "logs", label: "Jurnal", icon: <FileText className="h-4 w-4" /> },
    { key: "users", label: "Utilizatori", icon: <Users className="h-4 w-4" /> },
  ];

  return (
    <>
      <Helmet>
        <title>Moderare | Călimara</title>
      </Helmet>

      <div className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="font-display text-2xl font-medium text-primary mb-6 flex items-center gap-2">
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
            <StatCard label="În așteptare" value={stats.pending_count} icon={<Clock className="h-5 w-5 text-warning" />} />
            <StatCard label="Semnalate" value={stats.flagged_count} icon={<AlertTriangle className="h-5 w-5 text-danger" />} />
            <StatCard label="Suspendați" value={stats.suspended_count} icon={<Users className="h-5 w-5 text-muted" />} />
            <StatCard label="Acțiuni azi" value={stats.today_actions} icon={<CheckCircle className="h-5 w-5 text-success" />} />
          </div>
        )}

        {/* Pending / Flagged content */}
        {(activeTab === "pending" || activeTab === "flagged") && (
          <div className="space-y-3">
            {(activeTab === "pending" ? pending : flagged).map((item: ModerationItem) => (
              <Card key={`${item.type}-${item.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant={item.type === "post" ? "default" : "secondary"}>{item.type}</Badge>
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
                      <Button size="sm" variant="outline" onClick={() => { setActionModal({ type: item.type, id: item.id }); setActionChoice("approve"); }}>
                        <CheckCircle className="h-3.5 w-3.5 text-success" />
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => { setActionModal({ type: item.type, id: item.id }); setActionChoice("reject"); }}>
                        <XCircle className="h-3.5 w-3.5 text-danger" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {(activeTab === "pending" ? pending : flagged).length === 0 && (
              <div className="rounded-xl border border-border bg-surface-raised p-12 text-center">
                <p className="text-muted">Nimic de revizuit.</p>
              </div>
            )}
          </div>
        )}

        {/* AI Queue content */}
        {activeTab === "queue" && (
          <div className="space-y-3">
            {queue.map((item: ModerationQueueItem) => (
              <Card key={`log-${item.log_id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant={item.content_type === "post" ? "default" : "secondary"}>{item.content_type}</Badge>
                        <span className="text-sm font-medium text-primary">{item.content.author}</span>
                        <span className="text-xs text-muted">{formatDate(item.flagged_at)}</span>
                      </div>
                      
                      {item.content.title && <p className="font-medium text-primary">{item.content.title}</p>}
                      <p className="mt-1 text-sm text-muted whitespace-pre-wrap">{item.content.content}</p>
                      
                      <div className="mt-4 p-3 bg-danger/5 rounded-lg border border-danger/10">
                        <div className="flex items-center gap-2 text-danger text-sm font-medium mb-1">
                          <AlertTriangle className="h-4 w-4" />
                          Analiză AI: {item.ai_analysis.decision}
                        </div>
                        <p className="text-xs text-muted italic mb-2">"{item.ai_analysis.reason}"</p>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="danger" className="text-[10px] h-5">
                            Toxicitate: {(item.ai_analysis.toxicity_score * 100).toFixed(0)}%
                          </Badge>
                          {(item.ai_analysis.hate_speech_score || 0) > 0.1 && (
                            <Badge variant="danger" className="text-[10px] h-5">
                              Discurs ură: {((item.ai_analysis.hate_speech_score || 0) * 100).toFixed(0)}%
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-col gap-2 ml-4">
                      <Button 
                        size="sm" 
                        className="bg-success hover:bg-success/90 text-white" 
                        onClick={() => { setActionModal({ type: item.content_type, id: item.log_id, isLog: true }); setActionChoice("approve"); }}
                      >
                        <CheckCircle className="h-4 w-4 mr-1" /> Aprobă
                      </Button>
                      <Button 
                        size="sm" 
                        variant="danger"
                        onClick={() => { setActionModal({ type: item.content_type, id: item.log_id, isLog: true }); setActionChoice("reject"); }}
                      >
                        <XCircle className="h-4 w-4 mr-1" /> Respinge
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {queue.length === 0 && (
              <div className="rounded-xl border border-border bg-surface-raised p-12 text-center">
                <p className="text-muted">Nimic în coada AI.</p>
              </div>
            )}
          </div>
        )}

        {/* Logs */}
        {activeTab === "logs" && (
          <div className="space-y-3">
            {logs.map((log: ModerationLog) => (
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
                    <p className="mt-1 text-primary">Decizie umană: <Badge variant={log.human_decision === "approved" ? "success" : "danger"}>{log.human_decision}</Badge></p>
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
              placeholder="Caută utilizator..."
              value={userSearch}
              onChange={(e) => handleUserSearch(e.target.value)}
              className="mb-4 max-w-md"
            />
            <div className="space-y-2">
              {userData.map((u: ModerationUser) => (
                <div key={u.id} className="flex items-center justify-between rounded-lg border border-border bg-surface-raised p-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-primary">{u.username}</span>
                    {u.is_suspended && <Badge variant="danger">Suspendat</Badge>}
                  </div>
                  {u.is_suspended ? (
                    <Button size="sm" variant="outline" onClick={() => unsuspendMutation.mutate(u.id)}>Ridică suspendarea</Button>
                  ) : (
                    <Button size="sm" variant="danger" onClick={() => {
                      const reason = window.prompt("Motivul suspendării:");
                      if (reason) suspendMutation.mutate({ userId: u.id, reason });
                    }}>Suspendă</Button>
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
            <DialogTitle>{actionChoice === "approve" ? "Aprobă" : "Respinge"} conținutul</DialogTitle>
          </DialogHeader>
          <Input
            placeholder="Motiv (opțional)"
            value={actionReason}
            onChange={(e) => setActionReason(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setActionModal(null)}>Anulează</Button>
            <Button
              variant={actionChoice === "approve" ? "default" : "danger"}
              onClick={() => moderateMutation.mutate()}
              disabled={moderateMutation.isPending}
            >
              {actionChoice === "approve" ? "Aprobă" : "Respinge"}
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
