import type { Member, Tag, TagSummary, UserSummary } from "@/types/api";

/**
 * Writes send `assignee_ids` / `tag_ids`, but reads embed full objects.
 * These helpers resolve ids back into the embedded shapes so an optimistic
 * cache write can render avatars and tag chips immediately, in the same order
 * the user selected them.
 */
export function resolveAssignees(ids: string[], members: Member[]): UserSummary[] {
  const byId = new Map(members.map((m) => [m.user.id, m.user]));
  return ids
    .map((id) => byId.get(id))
    .filter((user): user is UserSummary => user !== undefined);
}

export function resolveTags(ids: string[], tags: Tag[]): TagSummary[] {
  const byId = new Map(tags.map((t) => [t.id, t]));
  return ids
    .map((id) => byId.get(id))
    .filter((tag): tag is Tag => tag !== undefined)
    .map(({ id, name, color }) => ({ id, name, color }));
}
