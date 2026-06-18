import { TicketDetailClient } from "./TicketDetailClient";

export async function generateStaticParams() {
  return [{ id: "__shell__" }];
}

export default function TicketDetailPage() {
  return <TicketDetailClient />;
}
