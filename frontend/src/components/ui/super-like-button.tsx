import type { ButtonHTMLAttributes } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import {
  fetchSuperLikeQuota,
  superLikePost,
  unSuperLikePost,
} from "@/api/superLikes";
import { ApiError } from "@/api/client";

type SuperLikeButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "onChange" | "onError"
> & {
  postId: number;
  postOwnerId: number;
  viewerId: number | null;
  superLikesCount: number;
  viewerSuperLiked: boolean;
  onChange?: (nextCount: number, nextLiked: boolean) => void;
  onError?: (message: string) => void;
};

function StarIcon({ active }: { active: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill={active ? "#D4AF37" : "none"}
      stroke={active ? "#D4AF37" : "currentColor"}
      strokeWidth="2"
      strokeLinejoin="round"
    >
      <polygon points="12 2 15 8.5 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 9 8.5 12 2" />
    </svg>
  );
}

export function SuperLikeButton({
  postId,
  postOwnerId,
  viewerId,
  superLikesCount,
  viewerSuperLiked,
  onChange,
  onError,
  className,
  ...rest
}: SuperLikeButtonProps) {
  const qc = useQueryClient();
  const isOwn = viewerId != null && viewerId === postOwnerId;
  const notLoggedIn = viewerId == null;

  const { data: quota } = useQuery({
    queryKey: ["super-like-quota"],
    queryFn: fetchSuperLikeQuota,
    enabled: !notLoggedIn,
    staleTime: 30_000,
  });

  const superMutation = useMutation<void, Error>({
    mutationFn: async () => {
      if (viewerSuperLiked) {
        await unSuperLikePost(postId);
      } else {
        await superLikePost(postId);
      }
    },
    onSuccess: () => {
      onChange?.(
        viewerSuperLiked ? Math.max(0, superLikesCount - 1) : superLikesCount + 1,
        !viewerSuperLiked,
      );
      qc.invalidateQueries({ queryKey: ["super-like-quota"] });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : "A apărut o eroare.";
      onError?.(msg);
    },
  });

  const outOfQuota =
    quota != null && quota.remaining <= 0 && !viewerSuperLiked;
  const disabled =
    notLoggedIn || isOwn || outOfQuota || superMutation.isPending;

  let title = "Super-apreciez";
  if (notLoggedIn) title = "Autentifică-te pentru a super-aprecia";
  else if (isOwn) title = "Nu îți poți super-aprecia propria postare";
  else if (outOfQuota && quota?.is_premium)
    title =
      "Ai folosit toate super-aprecierile săptămâna aceasta. Următoarele: luni.";
  else if (outOfQuota)
    title =
      "Ai folosit super-aprecierea săptămâna aceasta. Upgrade la Premium pentru 3 pe săptămână.";
  else if (quota)
    title = `Îți mai rămân ${quota.remaining} super-aprecieri săptămâna aceasta.`;

  return (
    <button
      type="button"
      className={cn(
        "react-btn react-super",
        viewerSuperLiked && "on",
        className,
      )}
      title={title}
      aria-pressed={viewerSuperLiked}
      disabled={disabled}
      onClick={() => superMutation.mutate()}
      {...rest}
    >
      <StarIcon active={viewerSuperLiked} />
      <span>Super-apreciez</span>
      {superLikesCount > 0 && (
        <span className="react-count">{superLikesCount}</span>
      )}
    </button>
  );
}
