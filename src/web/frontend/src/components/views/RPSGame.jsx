import React, { useState, useEffect, useCallback, useRef } from 'react';
import '../../styles/views/RPSGame.css';

const MOVES = ['ROCK', 'PAPER', 'SCISSORS'];

const ASSETS = {
    ROCK: '/images/rock.png',
    PAPER: '/images/paper.png',
    SCISSORS: '/images/scissors.png',
};

const WIN_CONDITIONS = {
    ROCK: 'SCISSORS',
    PAPER: 'ROCK',
    SCISSORS: 'PAPER',
};

const RPSGame = ({ wsEvent }) => {
    // Game State
    const [gameState, setGameState] = useState('idle'); // 'idle', 'waiting', 'revealed', 'resetting'
    const [playerMove, setPlayerMove] = useState(null);
    const [computerMove, setComputerMove] = useState(null);
    const [result, setResult] = useState(null);
    const [countdown, setCountdown] = useState(0);
    // Mode: automatic via WS events, or manual via on-screen buttons
    const [manualMode, setManualMode] = useState(false);
    // Difficulty for computer move randomness: 'low' (repeats sometimes), 'moderate' (avoid repeats), 'high' (fully random)
    const [difficulty, setDifficulty] = useState('moderate');

    // Stats
    const [score, setScore] = useState({ player: 0, computer: 0 });

    // Refs for logic
    const computerMoveRef = useRef(null);
    const processingRef = useRef(false);

    // Initialize Computer Move
    const pickComputerMove = useCallback(() => {
        const last = computerMoveRef.current;
        let choice;
        if (difficulty === 'low') {
            // slight bias to repeat last move (~60%) to make it more predictable
            if (last && Math.random() < 0.6) {
                choice = last;
            } else {
                choice = MOVES[Math.floor(Math.random() * MOVES.length)];
            }
        } else if (difficulty === 'moderate') {
            // avoid repeating the last move to increase variety
            const options = MOVES.filter((m) => m !== last);
            choice = options[Math.floor(Math.random() * options.length)];
        } else {
            // high = fully random
            choice = MOVES[Math.floor(Math.random() * MOVES.length)];
        }
        computerMoveRef.current = choice;
        setComputerMove(choice); // Stored but hidden until reveal
        console.log("Computer chose (hidden):", choice, "(difficulty:", difficulty, ")");
    }, [difficulty]);

    const resetGame = useCallback(() => {
        setGameState('idle');
        setPlayerMove(null);
        setResult(null);
        processingRef.current = false;
        pickComputerMove();
    }, [pickComputerMove]);

    // Connect on mount
    useEffect(() => {
        pickComputerMove();
    }, [pickComputerMove]);

    // Event Log State
    const [eventLogs, setEventLogs] = useState([]);

    // Handle Event via Prop (only if NOT in manual mode)
    useEffect(() => {
        if (!wsEvent) return;

        const eventName = wsEvent.event?.toUpperCase();

        // Add to log (keep last 10)
        setEventLogs(prev => [{
            id: Date.now() + Math.random(),
            time: new Date().toLocaleTimeString(),
            name: eventName,
            channel: wsEvent.channel
        }, ...prev].slice(0, 10));

        // Ignore WS events when manual mode is active
        if (manualMode) return;

        // Check if we are in waiting state
        if (gameState !== 'waiting' || processingRef.current) return;


        // Filter for RPS events
        if (MOVES.includes(eventName)) {
            handlePlayerMove(eventName);
        }
    }, [wsEvent, gameState, manualMode]);

    const handlePlayerMove = (pMove) => {
        // prevent double-processing
        if (processingRef.current) return;
        processingRef.current = true;
        const cMove = computerMoveRef.current || MOVES[Math.floor(Math.random() * MOVES.length)];

        setPlayerMove(pMove);
        setComputerMove(cMove); // Ensure it's set in state for rendering

        determineWinner(pMove, cMove);
        setGameState('revealed');

        // Auto reset after 3 seconds
        let count = 3;
        setCountdown(count);
        const interval = setInterval(() => {
            count--;
            setCountdown(count);
            if (count <= 0) {
                clearInterval(interval);
                resetGame();
            }
        }, 1000);
    };

    // Manual UI helpers
    const onManualMove = (move) => {
        // Only allow when waiting and not currently processing
        if (gameState !== 'waiting' || processingRef.current) return;
        handlePlayerMove(move);
    };

    const toggleManualMode = () => {
        // switching modes won't reset the current round, but will ignore WS events when manual
        setManualMode((v) => !v);
    };

    // Keyboard handling: map R / P / S to moves when in manual mode
    useEffect(() => {
        const onKeyDown = (ev) => {
            if (!manualMode) return;
            const k = ev.key.toLowerCase();
            if (k === 'r') onManualMove('ROCK');
            if (k === 'p') onManualMove('PAPER');
            if (k === 's') onManualMove('SCISSORS');
        };

        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [manualMode, gameState]);

    const determineWinner = (p, c) => {
        if (p === c) {
            setResult('TIE');
        } else if (WIN_CONDITIONS[p] === c) {
            setResult('WIN');
            setScore(prev => ({ ...prev, player: prev.player + 1 }));
        } else {
            setResult('LOSE');
            setScore(prev => ({ ...prev, computer: prev.computer + 1 }));
        }
    };

    // Helper for rendering card
    const renderCard = (type, move, revealed = true) => {
        const isWinner = result === 'WIN' && type === 'player' || result === 'LOSE' && type === 'computer';
        const isLoser = result === 'LOSE' && type === 'player' || result === 'WIN' && type === 'computer';

        let boxClass = 'card-box';
        if (revealed && result) {
            if (isWinner) boxClass += ' winner';
            if (isLoser) boxClass += ' loser';
        } else if (type === 'computer' && !revealed) {
            // active state?
        }

        return (
            <div className={boxClass}>
                <div className="card-label">{type === 'player' ? 'YOU' : 'COMPUTER'}</div>
                {revealed && move ? (
                    <img
                        src={ASSETS[move]}
                        alt={move}
                        className="card-image pop"
                        onError={(e) => {
                            e.target.onerror = null;
                            e.target.style.display = 'none';
                            e.target.parentNode.innerHTML += `<span style="font-size:4rem">${move === 'ROCK' ? '🪨' : move === 'PAPER' ? '📄' : '✂️'}</span>`
                        }}
                    />
                ) : (
                    <div className="card-placeholder">?</div>
                )}
            </div>
        );
    };

    const handlePlay = () => {
        setGameState('waiting');
        pickComputerMove();
    };

    return (
        <div className="rps-container">
            <div style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div className="rps-title">NEURO RPS</div>
                    <div className="top-controls">
                        <button className={`mode-btn ${manualMode ? 'active' : ''}`} onClick={toggleManualMode} title="Toggle manual mode">
                            {manualMode ? 'Manual' : 'Auto'}
                        </button>
                        <select className="difficulty-select" value={difficulty} onChange={(e) => setDifficulty(e.target.value)} title="Computer difficulty">
                            <option value="low">Low</option>
                            <option value="moderate">Moderate</option>
                            <option value="high">High</option>
                        </select>
                    </div>
                </div>
                <div className="scoreboard">
                    <div>Player: <strong>{score.player}</strong></div>
                    <div>Computer: <strong>{score.computer}</strong></div>
                </div>
            </div>

            <div className="status-text" style={{ minHeight: '60px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {gameState === 'idle' && (
                    <button
                        onClick={handlePlay}
                        className="px-8 py-2 bg-primary text-primary-contrast rounded-xl font-bold text-lg shadow-lg hover:scale-105 transition-transform animate-in zoom-in duration-300"
                    >
                        PLAY
                    </button>
                )}
                {gameState === 'waiting' && !manualMode && <span className="pulse">Waiting for Player Gesture...</span>}
                {gameState === 'waiting' && manualMode && <span className="pulse">Manual Mode: press <strong>R</strong>/<strong>P</strong>/<strong>S</strong></span>}
                {gameState !== 'waiting' && gameState !== 'idle' && <span>Result Received</span>}
            </div>



            <div className="cards-row">
                {renderCard('player', playerMove, !!playerMove)}

                <div className="vs-badge">VS</div>

                {/* Computer hidden until revealed */}
                {renderCard('computer', computerMove, gameState !== 'waiting')}
            </div>

            {gameState !== 'waiting' && result && (
                <div className="result-overlay">
                    <div className={`result-text ${result.toLowerCase()}`}>
                        {result === 'TIE' ? "IT'S A TIE" : `YOU ${result}!`}
                    </div>
                    <div style={{ marginTop: '1rem', color: '#888' }}>
                        Resetting in {countdown}...
                    </div>
                </div>
            )}

            {/* Event Log Panel */}
            <div className="mt-8 w-full max-w-2xl bg-surface/50 border border-white/5 rounded-lg p-4 backdrop-blur-sm">
                <div className="text-xs font-bold text-muted uppercase tracking-wider mb-2 flex justify-between items-center">
                    <span>Event Log</span>
                    <span className="text-[10px] opacity-60">Last 10 events</span>
                </div>
                <div className="space-y-1 font-mono text-xs max-h-[150px] overflow-y-auto">
                    {eventLogs.length === 0 ? (
                        <div className="text-muted/50 italic py-2 text-center">No events received yet...</div>
                    ) : (
                        eventLogs.map((log) => (
                            <div key={log.id} className="flex gap-3 py-1 border-b border-white/5 last:border-0 hover:bg-white/5 px-2 rounded">
                                <span className="text-muted">{log.time}</span>
                                <span className={`font-bold ${log.name === 'ROCK' ? 'text-amber-400' :
                                    log.name === 'PAPER' ? 'text-blue-400' :
                                        log.name === 'SCISSORS' ? 'text-pink-400' : 'text-text'
                                    }`}>
                                    {log.name}
                                </span>
                                <span className="text-muted ml-auto text-[10px]">{log.channel}</span>
                            </div>
                        ))
                    )}
                </div>
            </div>

        </div>
    );
};

export default RPSGame;
