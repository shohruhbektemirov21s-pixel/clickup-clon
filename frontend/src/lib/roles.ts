import type { PermissionGroupKey, Profession, Role, SpaceAccess } from "@/types/api";

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

/**
 * Kasb roli yorliqlari. DIQQAT: bu RUXSAT ROLI EMAS — `ROLE_LABEL` bilan
 * aralashtirmang. `profession` hech qanday vakolat bermaydi, u faqat profil
 * ma'lumoti (PM loyihaga mos odam tanlashi uchun).
 */
export const PROFESSION_LABEL: Record<Exclude<Profession, "">, string> = {
  project_manager: "Loyiha menejeri",
  developer: "Dasturchi",
  designer: "Dizayner",
  qa: "Tester",
  analyst: "Analitik",
  marketing: "Marketolog",
  other: "Boshqa",
};

/** Select uchun tartib — ro'yxatdan o'tish formasidagi ketma-ketlik. */
export const PROFESSION_OPTIONS = Object.entries(PROFESSION_LABEL) as [
  Exclude<Profession, "">,
  string,
][];

/** Roster ordering per the contract: owner, admin, member, guest, then email. */
export const ROLE_RANK: Record<Role, number> = {
  owner: 0,
  admin: 1,
  member: 2,
  guest: 3,
};

/** Column order of the permission matrix — highest privilege first. */
export const ROLE_COLUMNS: Role[] = ["owner", "admin", "member", "guest"];

/** Uzbek labels for `SpaceMember.access` (DESIGN_PERMISSIONS §E.1). */
export const SPACE_ACCESS_LABEL: Record<SpaceAccess, string> = {
  viewer: "Ko'ruvchi",
  contributor: "Ishtirokchi",
  manager: "Menejer (PM)",
};

/**
 * Uzbek labels for the permission catalog groups. The API already returns a
 * localised `label` per group; this is the offline fallback and keeps the
 * group order stable when the catalog has not loaded yet.
 */
export const PERMISSION_GROUP_LABEL: Record<PermissionGroupKey, string> = {
  workspace: "Ish maydoni",
  member: "A'zolar",
  space: "Bo'limlar",
  folder: "Jildlar",
  list: "Ro'yxatlar",
  task: "Vazifalar",
  comment: "Izohlar",
  attachment: "Biriktirmalar",
  tag: "Teglar",
};
