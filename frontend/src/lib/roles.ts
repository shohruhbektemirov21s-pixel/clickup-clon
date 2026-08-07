import type { Role } from "@/types/api";

/**
 * Uzbek display labels for workspace roles. Display only — the API always
 * sends and receives the English role values.
 */
export const ROLE_LABEL: Record<Role, string> = {
  owner: "Egasi",
  admin: "Admin",
  member: "A'zo",
  guest: "Mehmon",
};

/** Roster ordering per the contract: owner, admin, member, guest, then email. */
export const ROLE_RANK: Record<Role, number> = {
  owner: 0,
  admin: 1,
  member: 2,
  guest: 3,
};
