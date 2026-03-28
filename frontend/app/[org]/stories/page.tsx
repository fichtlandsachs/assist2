import { redirect } from "next/navigation";

export default async function StoriesPage({ params }: { params: Promise<{ org: string }> }) {
  const { org } = await params;
  redirect(`/${org}/stories/board`);
}
