"use client";

import * as React from "react";
import { useMe, useMyPermissions } from "@/hooks/queries";
import { contentPermissions, type ContentPermissions } from "@/lib/permissions";

/**
 * Ro'yxat ko'rinishi uchun ruxsat fasadi — doskadagi `useBoardPermissions`
 * bilan bir xil printsip.
 *
 * Ilgari bu yerda `canEdit={!isGuest}` turardi, ya'ni **rol** bo'yicha qaror.
 * Standart matritsa o'zgargach bu noto'g'ri bo'lib qoldi: oddiy `member`
 * begona vazifani tahrirlay olmaydi, faqat o'ziga biriktirilganini
 * (`task.update_assigned`); faqat o'qish (demo) hisobi esa roli `member`
 * bo'lsa ham hech narsa yoza olmaydi. Rolga qarab chizilgan UI serverdan
 * `403` oladigan tugmalarni ko'rsatardi.
 *
 * Qaror **bo'lim doirasida** olinadi (`canInSpace`), chunki server ham har
 * bir vazifa/komment/biriktirma yozuvida `has_space_perm` ni chaqiradi:
 * bo'lim `viewer` i ish maydoni darajasidagi `task.update` bilan ham hech
 * narsa yoza olmaydi (§B.5 — eng past huquq g'olib).
 *
 * ⚠️ Faqat UI affordance. Server har `PATCH`/`POST`/`DELETE` da qaytadan
 * tekshiradi (§C.4: 404 → 403 → 400).
 */
export type ListPermissions = ContentPermissions;

/**
 * @param workspaceId `my-permissions` so'rovi uchun.
 * @param spaceId Ro'yxat tegishli bo'lim (`List.space_id`). Hali yuklanmagan
 *   bo'lsa `undefined` bering — fasad `isLoading` holatiga tushadi va hech
 *   qanday yozish boshqaruvi yoqilmaydi.
 */
export function useListPermissions(
  workspaceId: string,
  spaceId: string | undefined,
): ListPermissions {
  const { data: my } = useMyPermissions(workspaceId);
  const { data: me } = useMe();
  const meId = me?.id;

  return React.useMemo(
    () => contentPermissions(my, spaceId, meId),
    [my, spaceId, meId],
  );
}
