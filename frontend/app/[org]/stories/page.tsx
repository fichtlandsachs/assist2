import { redirect } from "next/navigation";

export default function StoriesPage({ params }: { params: { org: string } }) {
  redirect(`/${params.org}/stories/board`);
}
