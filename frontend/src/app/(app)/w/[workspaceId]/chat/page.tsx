import { ChatView } from "@/components/chat/chat-view";

export default async function ChatPage({ params }: PageProps<"/w/[workspaceId]/chat">) {
  const { workspaceId } = await params;
  return <ChatView workspaceId={workspaceId} />;
}
