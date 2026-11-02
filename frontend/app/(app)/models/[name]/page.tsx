import { ModelDetailView } from "@/components/model-detail";
import { decodeRouteParam } from "@/components/models-ui";

export default async function ModelPage({
  params,
  searchParams,
}: {
  params: Promise<{ name: string }>;
  searchParams: Promise<{ id?: string }>;
}) {
  const { name } = await params;
  const { id } = await searchParams;
  return <ModelDetailView name={decodeRouteParam(name)} modelId={id ?? null} />;
}
