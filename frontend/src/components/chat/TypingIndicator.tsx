/** Three animated dots shown while waiting for the first token. */
export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="inline-block h-2 w-2 rounded-full bg-gray-400"
          style={{ animation: `blink 1.4s infinite both`, animationDelay: `${i * 0.2}s` }}
        />
      ))}
    </div>
  )
}
