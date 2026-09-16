export function ThemeFilter({
  value,
  themes,
  onChange,
}: {
  value: string;
  themes: string[];
  onChange(value: string): void;
}) {
  return (
    <label>
      Theme
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">All themes</option>
        {themes.map((theme) => (
          <option key={theme}>{theme}</option>
        ))}
      </select>
    </label>
  );
}
