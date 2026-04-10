import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { PenLine, Eye, Heart, MessageCircle, Trash2, Edit3, Settings, Users, Star, Link as LinkIcon } from "lucide-react";
import { fetchArchive, deletePost } from "@/api/posts";
import { updateUser, updateSocialLinks, updateBestFriends, updateFeaturedPosts, searchUsers, type SocialLinksData } from "@/api/users";
import { useAuth } from "@/hooks/useAuth";
import { useSubdomain } from "@/hooks/useSubdomain";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { generateAvatarSeeds } from "@/hooks/useDiceBearAvatar";
import { getAvatarUrl, formatDate, getBlogUrl } from "@/lib/utils";

export default function DashboardPage() {
  const { user, refetch: refetchAuth } = useAuth();
  const { username } = useSubdomain();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const { data: archiveData, isLoading } = useQuery({
    queryKey: ["posts", "archive"],
    queryFn: fetchArchive,
  });

  // Avatar management
  const [avatarSeeds, setAvatarSeeds] = useState(() => generateAvatarSeeds(6));
  const [selectedSeed, setSelectedSeed] = useState(user?.avatar_seed ?? "");
  const avatarMutation = useMutation({
    mutationFn: (seed: string) => updateUser({ avatar_seed: seed }),
    onSuccess: () => { refetchAuth(); showToast("Avatar actualizat!", "success"); },
  });

  // Subtitle
  const [subtitle, setSubtitle] = useState(user?.subtitle ?? "");
  const subtitleMutation = useMutation({
    mutationFn: (sub: string) => updateUser({ subtitle: sub }),
    onSuccess: () => { refetchAuth(); showToast("Subtitlu actualizat!", "success"); },
  });

  // Social links
  const [socialLinks, setSocialLinks] = useState<SocialLinksData>({});
  const socialMutation = useMutation({
    mutationFn: (data: SocialLinksData) => updateSocialLinks(data),
    onSuccess: () => showToast("Link-uri sociale actualizate!", "success"),
  });

  // Delete post
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const deleteMutation = useMutation({
    mutationFn: (id: number) => deletePost(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["posts", "archive"] });
      setDeleteId(null);
      showToast("Postare stearsa!", "success");
    },
  });

  useEffect(() => {
    if (user) {
      setSelectedSeed(user.avatar_seed);
      setSubtitle(user.subtitle ?? "");
    }
  }, [user]);

  if (isLoading || !user) return <PageLoader />;

  const posts = archiveData?.posts ?? [];

  return (
    <>
      <Helmet>
        <title>Panou de control | Calimara</title>
      </Helmet>

      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <h1 className="font-display text-2xl font-medium text-primary">Panou de control</h1>
          <Button asChild>
            <a href={`${getBlogUrl(user.username)}/create-post`} className="no-underline">
              <PenLine className="h-4 w-4" /> Postare noua
            </a>
          </Button>
        </div>

        <div className="grid gap-8 lg:grid-cols-3">
          {/* Posts List */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle>Postarile tale ({posts.length})</CardTitle>
              </CardHeader>
              <CardContent>
                {posts.length === 0 ? (
                  <p className="text-muted text-center py-8">Nu ai nicio postare inca.</p>
                ) : (
                  <div className="space-y-3">
                    {posts.map((post) => (
                      <div key={post.id} className="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-surface transition-colors">
                        <div className="min-w-0 flex-1">
                          <a href={`${getBlogUrl(user.username)}/${post.slug}`} className="font-medium text-primary hover:text-accent no-underline text-sm line-clamp-1">
                            {post.title}
                          </a>
                          <div className="flex items-center gap-3 mt-1 text-xs text-muted">
                            <Badge variant="default" className="text-[10px]">{post.category}</Badge>
                            <span>{formatDate(post.created_at)}</span>
                            <span className="flex items-center gap-0.5"><Eye className="h-3 w-3" /> {post.view_count}</span>
                            <span className="flex items-center gap-0.5"><Heart className="h-3 w-3" /> {post.likes_count}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1 ml-2">
                          <Button variant="ghost" size="icon" asChild className="h-8 w-8">
                            <a href={`${getBlogUrl(user.username)}/edit-post/${post.id}`}><Edit3 className="h-3.5 w-3.5" /></a>
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-danger hover:text-danger" onClick={() => setDeleteId(post.id)}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Sidebar Settings */}
          <div className="space-y-6">
            {/* Avatar */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2"><Settings className="h-4 w-4" /> Avatar</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-6 gap-2">
                  {avatarSeeds.map((seed) => (
                    <button
                      key={seed}
                      onClick={() => { setSelectedSeed(seed); avatarMutation.mutate(seed); }}
                      className={`rounded-full p-0.5 cursor-pointer ${selectedSeed === seed ? "ring-2 ring-accent" : "hover:ring-2 hover:ring-border"}`}
                    >
                      <img src={getAvatarUrl(seed, 48)} alt="" className="h-10 w-10 rounded-full" />
                    </button>
                  ))}
                </div>
                <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={() => setAvatarSeeds(generateAvatarSeeds(6))}>
                  Genereaza altele
                </Button>
              </CardContent>
            </Card>

            {/* Subtitle */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Subtitlu</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2">
                  <Input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} placeholder="Descriere scurta..." maxLength={100} />
                  <Button size="sm" onClick={() => subtitleMutation.mutate(subtitle)} disabled={subtitleMutation.isPending}>
                    Salveaza
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Social Links */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2"><LinkIcon className="h-4 w-4" /> Link-uri sociale</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {(["facebook_url", "instagram_url", "tiktok_url", "x_url", "bluesky_url"] as const).map((field) => (
                  <Input
                    key={field}
                    placeholder={field.replace("_url", "").replace("_", " ").replace(/^\w/, c => c.toUpperCase())}
                    value={(socialLinks as Record<string, string>)[field] ?? ""}
                    onChange={(e) => setSocialLinks({ ...socialLinks, [field]: e.target.value })}
                  />
                ))}
                <Button size="sm" className="w-full" onClick={() => socialMutation.mutate(socialLinks)} disabled={socialMutation.isPending}>
                  Salveaza link-urile
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Delete Confirmation */}
      <Dialog open={deleteId !== null} onOpenChange={() => setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sterge postarea</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted">Aceasta actiune este permanenta si nu poate fi anulata.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>Anuleaza</Button>
            <Button variant="danger" onClick={() => deleteId && deleteMutation.mutate(deleteId)} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending ? "Se sterge..." : "Sterge"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
