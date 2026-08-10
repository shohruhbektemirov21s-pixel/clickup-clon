"use client";

import * as React from "react";
import { useMe, useMyPermissions } from "@/hooks/queries";
import { can } from "@/lib/permissions";
import type { Task } from "@/types/api";

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
 * ⚠️ Faqat UI affordance. Server har `PATCH`/`POST` da qaytadan tekshiradi.
 */
export interface ListPermissions {
  /** Yangi vazifa yaratish (kompozitor va bo'sh holat tugmasi). */
  canCreate: boolean;
  /** Shu vazifa qatorining maydonlari tahrirlanadimi. */
  canEditTask: (task: Task) => boolean;
}

export function useListPermissions(
  workspaceId: string,
  enabled: boolean,
): ListPermissions {
  const { data: my } = useMyPermissions(workspaceId);
  const { data: me } = useMe();

  return React.useMemo(() => {
    if (!enabled) {
      return { canCreate: false, canEditTask: () => false };
    }
    const editAny = can(my, "task.update");
    const editAssigned = can(my, "task.update_assigned");
    return {
      canCreate: can(my, "task.create"),
      canEditTask: (task) =>
        editAny ||
        (editAssigned && task.assignees.some((a) => a.id === me?.id)),
    };
  }, [enabled, my, me?.id]);
}
