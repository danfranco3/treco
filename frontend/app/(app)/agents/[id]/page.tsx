import { AgentDetailClient } from "./AgentDetailClient";

export async function generateStaticParams() {
  return [{ id: "__shell__" }];
}

export default function AgentDetailPage() {
  return <AgentDetailClient />;
}
