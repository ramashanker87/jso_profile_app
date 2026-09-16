export function SearchBar({
  value,
  onChange,
  placeholder = "Search name, email, LinkedIn…",
}: {
  value: string;
  placeholder?: string;
  onChange(value: string): void;
}) {
  return (
    <label className="search">
      Search
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
