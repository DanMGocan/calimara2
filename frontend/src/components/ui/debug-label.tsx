export function DebugLabel({ name }: { name: string }) {
  return (
    <span className="debug-label" aria-hidden="true">
      {name}
    </span>
  );
}
