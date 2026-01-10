import React, { useState, useEffect, useRef } from 'react';
import { CalibrationApi } from '../../services/calibrationApi';

export default function TestPanel({
    activeSensor,
    activeChannelIndex,
    config,
    windowDuration = 1500,
    timeWindow = 5000,
    onStartRecording,
    onStopRecording,
    isRecording
}) {
    const [step, setStep] = useState('idle'); // idle, prompt, recording, processing, result
    const [targetGesture, setTargetGesture] = useState(null);
    const [prediction, setPrediction] = useState(null);
    const [score, setScore] = useState({ correct: 0, total: 0 });
    const [feedback, setFeedback] = useState(null); // 'correct', 'incorrect'

    // Available gestures based on sensor
    const getGestures = () => {
        if (activeSensor === 'EMG') return ['Rock', 'Paper', 'Scissors', 'Rest'];
        if (activeSensor === 'EOG') return ['SingleBlink', 'DoubleBlink', 'Rest'];
        return ['Rest'];
    };

    const startTest = () => {
        const gestures = getGestures();
        // Pick random gesture (excluding Rest sometimes? No, test Rest too)
        const random = gestures[Math.floor(Math.random() * gestures.length)];
        setTargetGesture(random);
        setStep('prompt');
        setPrediction(null);
        setFeedback(null);
    };

    const handleRecord = async () => {
        console.log("[TestPanel] Record clicked. Target:", targetGesture, "Handler Fn:", !!onStartRecording);
        if (!targetGesture) return;
        setStep('recording');

        // Let's assume parent passes `onCaptureWindow` which returns a promise resolving to result
        if (onStartRecording) {
            try {
                const result = await onStartRecording(targetGesture); // Generic "Test" label? No, pass target for logging
                // result should have { detected: bool, predicted_label: str }
                setPrediction(result.predicted_label || (result.detected ? targetGesture : "Rest"));
                setStep('result');
            } catch (e) {
                console.error("Test capture failed", e);
                setStep('idle');
            }
        }
    };

    const handleFeedback = (isCorrect) => {
        setScore(prev => ({
            correct: prev.correct + (isCorrect ? 1 : 0),
            total: prev.total + 1
        }));
        setFeedback(isCorrect ? 'correct' : 'incorrect');
        setStep('idle'); // or 'feedback_done'

        // Auto-next after short delay?
        setTimeout(startTest, 1500);
    };

    return (
        <div className="card bg-surface border border-border p-6 rounded-2xl shadow-card flex flex-col items-center justify-center gap-6 min-h-[300px]">
            {step === 'idle' && (
                <div className="text-center space-y-4">
                    <h3 className="text-lg font-bold">Ready to Test?</h3>
                    <p className="text-muted text-sm">Validate your calibration by performing random gestures.</p>
                    <button
                        onClick={startTest}
                        className="px-8 py-3 bg-primary text-primary-contrast rounded-xl font-bold text-lg shadow-lg hover:scale-105 transition-all"
                    >
                        Start Test
                    </button>
                    {score.total > 0 && (
                        <div className="text-xs font-mono text-muted uppercase tracking-widest mt-4">
                            Score: {score.correct}/{score.total} ({((score.correct / score.total) * 100).toFixed(0)}%)
                        </div>
                    )}
                </div>
            )}

            {step === 'prompt' && (
                <div className="text-center space-y-6 animate-in zoom-in duration-300">
                    <div className="text-sm font-bold text-muted uppercase tracking-widest">Please Perform</div>
                    <div className="text-5xl font-black text-primary drop-shadow-lg">{targetGesture}</div>
                    <div className="text-xs text-muted">Click below when ready</div>

                    <button
                        onClick={handleRecord}
                        disabled={isRecording}
                        className="px-8 py-4 bg-accent text-white rounded-xl font-bold text-xl shadow-xl hover:brightness-110 transition-all w-full max-w-[200px]"
                    >
                        {isRecording ? ' recording...' : 'GO!'}
                    </button>
                </div>
            )}

            {step === 'recording' && (
                <div className="flex flex-col items-center gap-4 animate-pulse">
                    <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center border-4 border-red-500">
                        <div className="w-4 h-4 bg-red-500 rounded-full"></div>
                    </div>
                    <div className="text-xl font-bold text-red-500">Listening...</div>
                    <div className="text-sm text-muted">Hold gesture steady</div>
                </div>
            )}

            {step === 'result' && prediction && (
                <div className="flex flex-col items-center gap-6 w-full max-w-sm animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="grid grid-cols-2 gap-8 w-full text-center">
                        <div className="space-y-1">
                            <div className="text-[10px] uppercase text-muted font-bold">Target</div>
                            <div className="text-xl font-bold text-text">{targetGesture}</div>
                        </div>
                        <div className="space-y-1">
                            <div className="text-[10px] uppercase text-muted font-bold">Predicted</div>
                            <div className={`text-xl font-bold ${prediction === targetGesture ? 'text-green-500' : 'text-red-500'}`}>
                                {prediction}
                            </div>
                        </div>
                    </div>

                    <div className="h-[1px] w-full bg-border"></div>

                    <div className="flex gap-4 w-full">
                        <button
                            onClick={() => handleFeedback(true)}
                            className="flex-1 py-3 bg-green-500/10 border border-green-500/20 text-green-500 rounded-xl font-bold hover:bg-green-500 hover:text-white transition-colors"
                        >
                            Correct
                        </button>
                        <button
                            onClick={() => handleFeedback(false)}
                            className="flex-1 py-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-xl font-bold hover:bg-red-500 hover:text-white transition-colors"
                        >
                            Incorrect
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
