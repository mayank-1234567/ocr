import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { Chess } from 'chess.js'
import { Chessboard } from 'react-chessboard'
import './App.css'

type Book = {
  id: number
  title: string
  import_status: string
  extraction_progress: number
  metadata_json: Record<string, unknown>
}

type Puzzle = {
  id: number
  book_id: number
  chapter?: string | null
  puzzle_number?: string | null
  fen?: string | null
  side_to_move?: string | null
  source_solution_text?: string | null
  parsed_solution_san: string[]
  extraction_confidence: number
  status: string
  source_type: string
}

type Dashboard = {
  total_puzzles: number
  verified_puzzles: number
  attempts: number
  correct_attempts: number
  avg_seconds: number
  books: { title: string; puzzles: number; avg_confidence: number }[]
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api',
})

function App() {
  const [tab, setTab] = useState<'library' | 'trainer' | 'dashboard'>('library')
  const [books, setBooks] = useState<Book[]>([])
  const [selectedBookId, setSelectedBookId] = useState<number | null>(null)
  const [puzzles, setPuzzles] = useState<Puzzle[]>([])
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [uploading, setUploading] = useState(false)
  const [mode, setMode] = useState<'sequential' | 'random'>('sequential')
  const [orientation, setOrientation] = useState<'white' | 'black'>((localStorage.getItem('orientation') as 'white' | 'black') || 'white')

  const [queue, setQueue] = useState<number[]>([])
  const [queueIndex, setQueueIndex] = useState(0)
  const [game, setGame] = useState(new Chess())
  const [attemptMoves, setAttemptMoves] = useState<string[]>([])
  const [hintCount, setHintCount] = useState(0)
  const [message, setMessage] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [stepIndex, setStepIndex] = useState(0)
  const [startedAt, setStartedAt] = useState<number>(Date.now())

  const currentPuzzle = useMemo(() => {
    if (!queue.length) return null
    const id = queue[queueIndex]
    return puzzles.find((p) => p.id === id) || null
  }, [puzzles, queue, queueIndex])

  useEffect(() => {
    void reloadBooks()
    void reloadDashboard()
  }, [])

  useEffect(() => {
    if (!selectedBookId) {
      setPuzzles([])
      return
    }
    void reloadPuzzles(selectedBookId)
  }, [selectedBookId])

  useEffect(() => {
    localStorage.setItem('orientation', orientation)
  }, [orientation])

  useEffect(() => {
    if (!currentPuzzle?.fen) return
    try {
      const next = new Chess(currentPuzzle.fen)
      setGame(next)
      setAttemptMoves([])
      setMessage('')
      setHintCount(0)
      setStepIndex(0)
      setStartedAt(Date.now())
    } catch {
      setMessage('Invalid FEN. Edit this puzzle in the review form.')
    }
  }, [currentPuzzle?.id])

  async function reloadBooks() {
    const { data } = await api.get<Book[]>('/books')
    setBooks(data)
    if (!selectedBookId && data[0]) setSelectedBookId(data[0].id)
  }

  async function reloadPuzzles(bookId: number) {
    const params = new URLSearchParams()
    params.set('book_id', String(bookId))
    if (statusFilter) params.set('status', statusFilter)
    const { data } = await api.get<Puzzle[]>(`/puzzles?${params.toString()}`)
    setPuzzles(data)
  }

  async function reloadDashboard() {
    const { data } = await api.get<Dashboard>('/dashboard')
    setDashboard(data)
  }

  async function onUpload(file: File) {
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      await api.post('/books/upload', form)
      setMessage('Upload started. Refresh in a few seconds for extraction progress.')
      await reloadBooks()
    } catch {
      setMessage('Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function startTraining() {
    if (!selectedBookId) return
    const { data } = await api.post<{ puzzle_ids: number[] }>('/trainer/session', {
      book_id: selectedBookId,
      mode,
      include_statuses: ['verified', 'needs_review', 'engine_generated'],
    })
    setQueue(data.puzzle_ids)
    setQueueIndex(0)
    setTab('trainer')
  }

  function nextExpectedSan(): string | null {
    if (!currentPuzzle?.parsed_solution_san?.length) return null
    return currentPuzzle.parsed_solution_san[stepIndex] ?? null
  }

  async function onMove(from: string, to: string) {
    if (!currentPuzzle) return false
    const expected = nextExpectedSan()
    const working = new Chess(game.fen())
    const move = working.move({ from, to, promotion: 'q' })
    if (!move) return false

    const san = move.san
    const line = currentPuzzle.parsed_solution_san || []

    if (expected && san !== expected) {
      setMessage(`Incorrect move (${san}). Expected tactical line starts differently.`)
      setAttemptMoves((prev) => [...prev, san])
      await logAttempt(false, [...attemptMoves, san])
      return false
    }

    let idx = stepIndex + 1
    if (line[idx]) {
      try {
        const reply = working.move(line[idx], { sloppy: true })
        if (reply) idx += 1
      } catch {
        // keep position if reply cannot be applied
      }
    }

    setAttemptMoves((prev) => [...prev, san])
    setGame(working)
    setStepIndex(idx)

    if (!line.length || idx >= line.length) {
      setMessage('Correct! Moving to next puzzle...')
      await logAttempt(true, [...attemptMoves, san], true)
      setTimeout(() => {
        setQueueIndex((v) => Math.min(v + 1, queue.length - 1))
      }, 700)
    } else {
      setMessage('Good move. Continue the line.')
    }
    return true
  }

  async function logAttempt(correctness: boolean, moves: string[], firstAttempt = false) {
    if (!currentPuzzle) return
    await api.post('/attempts', {
      puzzle_id: currentPuzzle.id,
      moves_played_san: moves,
      correctness,
      hints_used: hintCount,
      duration_seconds: (Date.now() - startedAt) / 1000,
      training_mode: mode,
      first_attempt: firstAttempt,
    })
    await reloadDashboard()
  }

  function undoMove() {
    const copy = new Chess(game.fen())
    copy.undo()
    setGame(copy)
  }

  function restartPuzzle() {
    if (!currentPuzzle?.fen) return
    setGame(new Chess(currentPuzzle.fen))
    setStepIndex(0)
    setAttemptMoves([])
    setHintCount(0)
    setMessage('Puzzle restarted')
  }

  function revealHint() {
    const expected = nextExpectedSan()
    if (!expected) return
    setHintCount((v) => v + 1)
    if (hintCount === 0) setMessage(`Hint: candidate move begins with ${expected[0]}`)
    else if (hintCount === 1) setMessage(`Hint: move is ${expected.slice(0, 2)}...`)
    else setMessage(`Hint: play ${expected}`)
  }

  function revealSolution() {
    if (!currentPuzzle) return
    const working = new Chess(game.fen())
    for (const san of currentPuzzle.parsed_solution_san.slice(stepIndex)) {
      try {
        working.move(san, { sloppy: true })
      } catch {
        break
      }
    }
    setGame(working)
    setStepIndex(currentPuzzle.parsed_solution_san.length)
    setMessage('Solution shown')
  }

  async function updatePuzzle(puzzle: Puzzle, patch: Partial<Puzzle>) {
    await api.patch(`/puzzles/${puzzle.id}`, patch)
    if (selectedBookId) await reloadPuzzles(selectedBookId)
  }

  return (
    <div className="app">
      <header>
        <h1>Universal Chess Tactics Book Trainer</h1>
        <div className="tabs">
          <button onClick={() => setTab('library')}>Library</button>
          <button onClick={() => setTab('trainer')}>Trainer</button>
          <button onClick={() => setTab('dashboard')}>Dashboard</button>
        </div>
      </header>

      {tab === 'library' && (
        <section className="panel">
          <h2>Library</h2>
          <input type="file" accept="application/pdf" onChange={(e) => e.target.files?.[0] && void onUpload(e.target.files[0])} />
          {uploading && <p>Uploading...</p>}
          <div className="row">
            <label>
              Book:
              <select value={selectedBookId ?? ''} onChange={(e) => setSelectedBookId(Number(e.target.value))}>
                <option value="">Select</option>
                {books.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.title} ({b.import_status} {Math.round(b.extraction_progress * 100)}%)
                  </option>
                ))}
              </select>
            </label>
            <label>
              Status:
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="">All</option>
                <option value="verified">Verified</option>
                <option value="needs_review">Needs review</option>
                <option value="engine_generated">Engine-generated</option>
                <option value="duplicate">Duplicate</option>
              </select>
            </label>
            <button onClick={() => selectedBookId && void reloadPuzzles(selectedBookId)}>Refresh puzzles</button>
          </div>

          <div className="puzzle-list">
            {puzzles.map((p) => (
              <article key={p.id} className="card">
                <strong>#{p.puzzle_number ?? p.id}</strong> · {p.chapter ?? 'No chapter'}
                <div>status: {p.status}</div>
                <div>confidence: {(p.extraction_confidence * 100).toFixed(1)}%</div>
                <div>FEN: {p.fen}</div>
                <div>line: {p.parsed_solution_san.join(' ') || '(none)'}</div>
                <div className="row">
                  <button onClick={() => void updatePuzzle(p, { status: 'verified' })}>Mark verified</button>
                  <button onClick={() => {
                    const fen = prompt('Correct FEN', p.fen ?? '')
                    if (fen) void updatePuzzle(p, { fen, status: 'verified' })
                  }}>Edit FEN</button>
                  <button onClick={() => {
                    const line = prompt('Solution SAN line', (p.parsed_solution_san || []).join(' '))
                    if (line !== null) void updatePuzzle(p, { parsed_solution_san: line.split(/\s+/).filter(Boolean) })
                  }}>Edit line</button>
                </div>
              </article>
            ))}
          </div>

          <div className="row">
            <label>
              Mode:
              <select value={mode} onChange={(e) => setMode(e.target.value as 'sequential' | 'random')}>
                <option value="sequential">Sequential</option>
                <option value="random">Random</option>
              </select>
            </label>
            <button onClick={() => void startTraining()}>Start training</button>
          </div>
        </section>
      )}

      {tab === 'trainer' && (
        <section className="panel trainer-grid">
          <div>
            <h2>Trainer</h2>
            <p>
              Puzzle {queueIndex + 1}/{queue.length} {currentPuzzle ? `· #${currentPuzzle.puzzle_number ?? currentPuzzle.id}` : ''}
            </p>
            <Chessboard
              id="trainer-board"
              position={game.fen()}
              onPieceDrop={(sourceSquare, targetSquare) => {
                void onMove(sourceSquare, targetSquare)
                return true
              }}
              boardOrientation={orientation}
            />
            <div className="row wrap">
              <button onClick={undoMove}>Undo</button>
              <button onClick={restartPuzzle}>Restart</button>
              <button onClick={revealHint}>Hint</button>
              <button onClick={revealSolution}>Reveal solution</button>
              <button onClick={() => setQueueIndex((i) => Math.max(0, i - 1))}>Prev</button>
              <button onClick={() => setQueueIndex((i) => Math.min(queue.length - 1, i + 1))}>Next</button>
              <button onClick={() => setOrientation((o) => (o === 'white' ? 'black' : 'white'))}>Flip</button>
            </div>
            <p className="msg">{message}</p>
          </div>
          <div>
            <h3>Move list</h3>
            <pre>{game.history().join(' ') || '(empty)'}</pre>
            <h3>Expected line</h3>
            <pre>{currentPuzzle?.parsed_solution_san.join(' ') || '(none)'}</pre>
            <h3>Source</h3>
            <p>{currentPuzzle?.source_solution_text || 'No parsed source text'}</p>
          </div>
        </section>
      )}

      {tab === 'dashboard' && (
        <section className="panel">
          <h2>Progress Dashboard</h2>
          {!dashboard ? (
            <p>Loading...</p>
          ) : (
            <>
              <div className="metrics">
                <div>Total puzzles: {dashboard.total_puzzles}</div>
                <div>Verified: {dashboard.verified_puzzles}</div>
                <div>Attempts: {dashboard.attempts}</div>
                <div>Correct: {dashboard.correct_attempts}</div>
                <div>Avg sec: {dashboard.avg_seconds.toFixed(1)}</div>
              </div>
              <h3>By book</h3>
              <ul>
                {dashboard.books.map((b) => (
                  <li key={b.title}>
                    {b.title}: {b.puzzles} puzzles, avg confidence {(b.avg_confidence * 100).toFixed(1)}%
                  </li>
                ))}
              </ul>
              <button onClick={() => void reloadDashboard()}>Refresh</button>
            </>
          )}
        </section>
      )}
    </div>
  )
}

export default App
