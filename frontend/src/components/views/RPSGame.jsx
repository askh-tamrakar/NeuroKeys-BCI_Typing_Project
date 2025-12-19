import React, { useState, useEffect, useCallback, useRef } from 'react';
import '../../styles/RPSGame.css';

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
    const [gameState, setGameState] = useState('waiting'); // 'waiting', 'revealed', 'resetting'
    const [playerMove, setPlayerMove] = useState(null);
    const [computerMove, setComputerMove] = useState(null);
    const [result, setResult] = useState(null);
    const [countdown, setCountdown] = useState(0);

    // Stats
    const [score, setScore] = useState({ player: 0, computer: 0 });

    // Refs for logic
    const computerMoveRef = useRef(null);
    const processingRef = useRef(false);

    // Initialize Computer Move
    const pickComputerMove = useCallback(() => {
        const randomMove = MOVES[Math.floor(Math.random() * MOVES.length)];
        computerMoveRef.current = randomMove;
        setComputerMove(randomMove); // Stored but hidden event in Waiting state
        console.log("Computer chose (hidden):", randomMove);
    }, []);

    const resetGame = useCallback(() => {
        setGameState('waiting');
        setPlayerMove(null);
        setResult(null);
        processingRef.current = false;
        pickComputerMove();
    }, [pickComputerMove]);

    // Connect on mount
    useEffect(() => {
        pickComputerMove();
    }, [pickComputerMove]);

    // Handle Event via Prop
    useEffect(() => {
        if (!wsEvent) return;

        // Check if we are in waiting state
        if (gameState !== 'waiting' || processingRef.current) return;

        const eventName = wsEvent.event?.toUpperCase();

        // Filter for RPS events
        if (MOVES.includes(eventName)) {
            handlePlayerMove(eventName);
        }
    }, [wsEvent, gameState]);

    const handlePlayerMove = (pMove) => {
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

    return (
        <div className="rps-container">
            <div className="rps-title">NEURO RPS</div>

            <div className="status-text">
                {gameState === 'waiting' && <span className="pulse">Waiting for Player Gesture...</span>}
                {gameState !== 'waiting' && <span>Result Recieved</span>}
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

            <div style={{
                position: 'absolute',
                bottom: '20px',
                display: 'flex',
                gap: '2rem',
                background: 'rgba(0,0,0,0.4)',
                padding: '10px 20px',
                borderRadius: '30px'
            }}>
                <div>Player: <strong>{score.player}</strong></div>
                <div>Computer: <strong>{score.computer}</strong></div>
            </div>

        </div>
    );
};

export default RPSGame;
