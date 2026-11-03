import { ModelVersionView } from "@/components/model-version-detail";
import { decodeRouteParam } from "@/components/models-ui";

export default async function ModelVersionPage({
  params,
  searchParams,
}: {
  params: Promise<{ name: string; version: string }>;
  searchParams: Promise<{ id?: string }>;
}) {
  const { name, version } = await params;
  const { id } = await searchParams;
  return <ModelVersionView name={decodeRouteParam(name)} modelId={id ?? null} version={Number(version)} />;
}
