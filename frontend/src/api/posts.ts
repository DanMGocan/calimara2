import { api } from "./client";

export interface Post {
  id: number;
  user_id: number;
  title: string;
  slug: string;
  content: string;
  category: string;
  category_name?: string;
  view_count: number;
  likes_count: number;
  comments_count?: number;
  moderation_status: string;
  created_at: string;
  updated_at: string;
  tags?: Tag[];
  owner?: PostOwner;
}

export interface PostOwner {
  id: number;
  username: string;
  avatar_seed: string;
  subtitle: string | null;
}

export interface Tag {
  id: number;
  tag_name: string;
}

export interface Comment {
  id: number;
  post_id: number;
  user_id: number | null;
  author_name: string;
  author_email: string | null;
  content: string;
  approved: boolean;
  moderation_status: string;
  created_at: string;
  user?: { username: string; avatar_seed: string } | null;
}

export interface Like {
  id: number;
  post_id: number;
  user_id: number | null;
  ip_address: string | null;
}

// Landing page
export interface LandingData {
  random_posts: Post[];
}

export interface BlogUser {
  id: number;
  username: string;
  subtitle: string | null;
  avatar_seed: string;
}

export function fetchLanding(category = "toate"): Promise<LandingData> {
  return api.get(`/api/landing?category=${encodeURIComponent(category)}`);
}

// Blog page
export interface BlogData {
  blog_owner: BlogUser & {
    facebook_url?: string;
    tiktok_url?: string;
    instagram_url?: string;
    x_url?: string;
    bluesky_url?: string;
    patreon_url?: string;
    paypal_url?: string;
    buymeacoffee_url?: string;
  };
  featured_posts: Post[];
  latest_posts: Post[];
  all_posts: Post[];
  available_months: { month: number; year: number; count: number }[];
  blog_categories: string[];
  best_friends: { user: BlogUser; position: number }[];
  user_awards: Award[];
  total_likes: number;
  total_comments: number;
}

export interface Award {
  id: number;
  award_title: string;
  award_description: string;
  award_date: string;
  award_type: string;
}

export function fetchBlog(username: string, month?: number, year?: number): Promise<BlogData> {
  const params = new URLSearchParams();
  if (month) params.set("month", String(month));
  if (year) params.set("year", String(year));
  const qs = params.toString();
  return api.get(`/api/blog/${username}${qs ? `?${qs}` : ""}`);
}

// Post detail
export interface PostDetailData {
  blog_owner: BlogUser;
  post: Post & { approved_comments: Comment[] };
  related_posts: Post[];
  other_authors: BlogUser[];
}

export function fetchPostDetail(username: string, slug: string): Promise<PostDetailData> {
  return api.get(`/api/blog/${username}/post/${slug}`);
}

// Category page
export interface CategoryPageData {
  category_key: string;
  category_name: string;
  posts: Post[];
  sort_by: string;
}

export function fetchCategoryPage(categoryKey: string, sortBy = "newest"): Promise<CategoryPageData> {
  return api.get(`/api/categories/${categoryKey}?sort_by=${sortBy}`);
}

// Post CRUD
export function fetchArchive(): Promise<{ posts: Post[] }> {
  return api.get("/api/posts/archive");
}

export interface PostCreateData {
  title: string;
  content: string;
  tags?: string[];
}

export function createPost(data: PostCreateData): Promise<Post> {
  return api.post("/api/posts/", data);
}

export function updatePost(postId: number, data: Partial<PostCreateData>): Promise<Post> {
  return api.put(`/api/posts/${postId}`, data);
}

export function deletePost(postId: number): Promise<void> {
  return api.delete(`/api/posts/${postId}`);
}

// Comments
export interface CommentCreateData {
  content: string;
  author_name?: string;
  author_email?: string;
}

export function createComment(postId: number, data: CommentCreateData): Promise<Comment> {
  return api.post(`/api/posts/${postId}/comments`, data);
}

// Likes
export function toggleLike(postId: number): Promise<Like> {
  return api.post(`/api/posts/${postId}/likes`);
}
