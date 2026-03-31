interface ActorColumnProps {
  title: string;
  actors: string[];
  accentColor: string;
}

export default function ActorColumn({
  title,
  actors,
  accentColor,
}: ActorColumnProps) {
  return (
    <div
      style={{
        background: "var(--bg-tertiary)",
        border: "1px solid var(--border-secondary)",
        borderRadius: 8,
        padding: 12,
      }}
    >
      <div style={{ fontSize: 10, fontWeight: 600, color: accentColor, marginBottom: 8, textTransform: "uppercase" as const, letterSpacing: "0.04em" }}>
        {title}
      </div>
      {actors.length === 0 ? (
        <div style={{ fontSize: 11, color: "var(--text-muted)", fontStyle: "italic" }}>없음</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {actors.map((actor) => (
            <div
              key={actor}
              style={{
                fontSize: 11,
                color: "var(--text-primary)",
                padding: "3px 8px",
                background: `${accentColor}10`,
                borderRadius: 4,
              }}
            >
              {actor}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
