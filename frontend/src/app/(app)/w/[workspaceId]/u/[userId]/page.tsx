import { MemberProfile } from "@/components/workspace/member-profile";

export default async function MemberProfilePage({
  params,
}: PageProps<"/w/[workspaceId]/u/[userId]">) {
  const { workspaceId, userId } = await params;
  return <MemberProfile workspaceId={workspaceId} userId={userId} />;
}
