import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { inviteToClub } from "@/api/clubs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast-context";

interface Props {
  clubId: number;
  clubSlug: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function InviteUserDialog({ clubId, clubSlug, open, onOpenChange }: Props) {
  const [username, setUsername] = useState("");
  const { showToast } = useToast();
  const qc = useQueryClient();

  const invite = useMutation({
    mutationFn: () => inviteToClub(clubId, username.trim()),
    onSuccess: () => {
      showToast(`Invitație trimisă către ${username}`, "success");
      setUsername("");
      onOpenChange(false);
      qc.invalidateQueries({ queryKey: ["clubs", clubId, "requests"] });
      qc.invalidateQueries({ queryKey: ["clubs", "bySlug", clubSlug] });
    },
    onError: (e: Error) => showToast(e.message || "Invitația nu a putut fi trimisă", "danger"),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <span style={{ display: "none" }} />
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invită un membru</DialogTitle>
          <DialogDescription>
            Introdu numele de utilizator. Persoana va primi o notificare cu invitația.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!username.trim()) return;
            invite.mutate();
          }}
        >
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="nume_utilizator"
            className="cal-input"
            style={{ width: "100%" }}
            autoFocus
          />
          <DialogFooter>
            <button
              type="button"
              className="cal-btn"
              onClick={() => onOpenChange(false)}
            >
              Anulează
            </button>
            <button
              type="submit"
              className="cal-btn"
              disabled={invite.isPending || !username.trim()}
            >
              {invite.isPending ? "Se trimite..." : "Trimite invitația"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
