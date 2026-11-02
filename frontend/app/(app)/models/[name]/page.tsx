import { ModelDetailView } from "@/components/model-detail";

export default async function ModelPage({
  params,
  searchParams,
}: {
  params: Promise<{ name: string }>;
  searchParams: Promise<{ id?: string }>;
}) {
  const { name } = await params;
  const { id } = await searchParams;
  return <ModelDetailView name={name} modelId={id ?? null} />;
}
