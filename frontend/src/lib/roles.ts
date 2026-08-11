import type { Role } from "@/types/api";

/**
 * Rol TARTIBI. Yorliqlar bu yerda emas — ular `src/i18n/uz.ts` da
 * (`ROLE_LABEL`, `PROFESSION_LABEL`, `SPACE_ACCESS_LABEL`,
 * `PERMISSION_GROUP_LABEL`). Bu faylda faqat ekranga chiqmaydigan tartib
 * qoladi, ya'ni matn va tartib bir-biriga aralashmaydi.
 */

/** Roster ordering per the contract: owner, admin, member, guest, then email. */
export const ROLE_RANK: Record<Role, number> = {
  owner: 0,
  admin: 1,
  member: 2,
  guest: 3,
};

/** Column order of the permission matrix — highest privilege first. */
export const ROLE_COLUMNS: Role[] = ["owner", "admin", "member", "guest"];
