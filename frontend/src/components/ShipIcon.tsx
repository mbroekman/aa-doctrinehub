export function ShipIcon({ typeId, size = 32 }: { typeId: number | null; size?: number }) {
  if (!typeId) {
    return <div className="rounded bg-muted" style={{ width: size, height: size }} />;
  }
  return (
    <img
      src={`https://images.evetech.net/types/${typeId}/icon?size=64`}
      alt=""
      width={size}
      height={size}
      className="rounded"
      loading="lazy"
    />
  );
}
