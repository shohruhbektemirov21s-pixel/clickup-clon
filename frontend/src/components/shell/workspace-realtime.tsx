import * as React from "react";
import {
  useWorkspaceChannel,
  type WorkspaceConnectionStatus,
} from "@/hooks/use-workspace-channel";

const WorkspaceConnectionContext =
  React.createContext<WorkspaceConnectionStatus>("connecting");

/**
 * Ish maydoni soketi — BUTUN shell uchun bitta.
 *
 * Ilgari `useWorkspaceChannel` faqat bosh sahifada (`WorkspaceHome`) chaqirilardi,
 * ya'ni ro'yxat yoki sozlamalar sahifasida turgan odam jonli freymlarni umuman
 * olmasdi. Qo'ng'iroqcha esa `TopBar` da, ya'ni HAR BIR sahifada turadi va
 * `notification.created` aynan shu soketdan keladi — demak kanal shelldan
 * yuqoriroq bo'lishi shart.
 *
 * Hookni ikkinchi marta chaqirish ikkinchi soket ochardi (ikki handshake,
 * ikki karra invalidatsiya), shuning uchun holat kontekst orqali tarqatiladi:
 * provider — yagona egasi, iste'molchilar faqat o'qiydi.
 */
export function WorkspaceRealtimeProvider({
  workspaceId,
  children,
}: {
  workspaceId: string;
  children: React.ReactNode;
}) {
  const status = useWorkspaceChannel(workspaceId);
  return (
    <WorkspaceConnectionContext.Provider value={status}>
      {children}
    </WorkspaceConnectionContext.Provider>
  );
}

/** Joriy ish maydoni soketining holati (`connecting` — provider yo'q bo'lsa). */
export function useWorkspaceConnection(): WorkspaceConnectionStatus {
  return React.useContext(WorkspaceConnectionContext);
}
