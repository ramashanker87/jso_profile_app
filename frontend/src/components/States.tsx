export function LoadingState({ label = "profiles" }: { label?: string }) {
  return (
    <p className="state" role="status">
      Loading {label}…
    </p>
  );
}
export function ErrorState({ message }: { message: string }) {
  return (
    <p className="error" role="alert">
      {message}
    </p>
  );
}
export function EmptyState() {
  return (
    <div className="state">
      <h2>No submissions found</h2>
      <p>Try a different search or synchronize your form submissions.</p>
    </div>
  );
}
