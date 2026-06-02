import type { SSEEvent } from './types'

/**
 * Async generator that reads a Fetch Response body and yields parsed SSE events.
 *
 * Handles chunk boundaries correctly: buffers incomplete data between reads and
 * splits on the blank-line (double-newline) event separator.
 */
export async function* parseSSE(response: Response): AsyncGenerator<SSEEvent> {
  if (!response.body) throw new Error('Response has no body')

  const reader  = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer    = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // Each SSE event is terminated by \n\n
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''       // last part may be incomplete

    for (const block of blocks) {
      if (!block.trim()) continue

      let eventType = ''
      let dataStr   = ''

      for (const line of block.split('\n')) {
        if (line.startsWith('event: '))      eventType = line.slice(7).trim()
        else if (line.startsWith('data: '))  dataStr   = line.slice(6).trim()
      }

      if (!dataStr) continue

      try {
        const parsed = JSON.parse(dataStr)
        yield { event: eventType, data: parsed } as SSEEvent
      } catch {
        // malformed JSON — skip
      }
    }
  }
}
