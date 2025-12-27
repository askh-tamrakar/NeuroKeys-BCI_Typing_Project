import React, { useState } from 'react';
import Tree from 'react-d3-tree';

export default function MLTrainingView() {
    const [params, setParams] = useState({
        n_estimators: 300,
        max_depth: 8,
        test_size: 0.3
    });

    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setParams(prev => ({
            ...prev,
            [name]: name === 'test_size' ? parseFloat(value) : parseInt(value)
        }));
    };

    const startTraining = async () => {
        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const response = await fetch('http://localhost:5000/api/train-emg-rf', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(params),
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || errData.error || 'Training failed');
            }

            const data = await response.json();
            setResult(data);
        } catch (err) {
            console.error(err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Helper to style the tree nodes if needed
    const renderCustomNodeElement = ({ nodeDatum, toggleNode }) => (
        <g>
            <circle r="15" fill="var(--primary)" stroke="var(--border)" onClick={toggleNode} />
            <text fill="var(--text)" x="20" dy="5" strokeWidth="0">
                {nodeDatum.name}
            </text>
            {nodeDatum.attributes && (
                <text fill="var(--muted)" x="20" dy="25" strokeWidth="0" fontSize="10">
                    {Object.entries(nodeDatum.attributes).map(([k, v]) => `${k}: ${v}`).join(', ')}
                </text>
            )}
        </g>
    );

    return (
        <div className="container py-8 font-sans transition-colors duration-300">
            <h1 className="text-3xl font-bold mb-6 text-[var(--accent)]">EMG Random Forest Training</h1>

            {/* Controls */}
            <div className="card mb-8 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                <div>
                    <label className="block text-sm font-medium mb-1 text-[var(--text)]">Results (Trees)</label>
                    <input
                        type="number"
                        name="n_estimators"
                        value={params.n_estimators}
                        onChange={handleInputChange}
                        className="input"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium mb-1 text-[var(--text)]">Max Depth</label>
                    <input
                        type="number"
                        name="max_depth"
                        value={params.max_depth}
                        onChange={handleInputChange}
                        className="input"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium mb-1 text-[var(--text)]">Test Size (0.1 - 0.5)</label>
                    <input
                        type="number"
                        step="0.05"
                        name="test_size"
                        value={params.test_size}
                        onChange={handleInputChange}
                        className="input"
                    />
                </div>
                <button
                    onClick={startTraining}
                    disabled={loading}
                    className="btn w-full h-[46px]"
                >
                    {loading ? 'Training...' : 'Train Model'}
                </button>
            </div>

            {error && (
                <div className="bg-red-900/20 border border-red-500 text-red-200 px-4 py-3 rounded mb-6">
                    <strong>Error:</strong> {error}
                </div>
            )}

            {result && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Metrics */}
                    <div className="space-y-6">
                        <div className="card">
                            <h2 className="text-xl font-semibold mb-4 border-b border-[var(--border)] pb-2 text-[var(--text)]">Model Performance</h2>
                            <div className="text-4xl font-bold text-[var(--primary)] mb-2">
                                {(result.accuracy * 100).toFixed(2)}%
                            </div>
                            <p className="text-[var(--muted)] uppercase text-xs tracking-wider">Accuracy Score</p>
                        </div>

                        <div className="card">
                            <h2 className="text-xl font-semibold mb-4 border-b border-[var(--border)] pb-2 text-[var(--text)]">Confusion Matrix</h2>
                            <div className="overflow-x-auto">
                                <table className="min-w-full text-sm text-left text-[var(--text)]">
                                    <thead>
                                        <tr className="bg-[var(--bg)]">
                                            <th className="p-2">Actual \ Pred</th>
                                            <th className="p-2">Rest</th>
                                            <th className="p-2">Rock</th>
                                            <th className="p-2">Paper</th>
                                            <th className="p-2">Scissors</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {result.confusion_matrix.map((row, i) => (
                                            <tr key={i} className="border-b border-[var(--border)]">
                                                <td className="p-2 font-medium bg-[var(--surface)] text-[var(--accent)]">
                                                    {['Rest', 'Rock', 'Paper', 'Scissors'][i]}
                                                </td>
                                                {row.map((cell, j) => (
                                                    <td key={j} className={`p-2 ${i === j ? 'bg-[var(--primary)] text-[var(--primary-contrast)] font-bold' : ''}`}>
                                                        {cell}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="card">
                            <h2 className="text-xl font-semibold mb-4 border-b border-[var(--border)] pb-2 text-[var(--text)]">Feature Importance</h2>
                            <ul className="space-y-2">
                                {Object.entries(result.feature_importances)
                                    .sort(([, a], [, b]) => b - a)
                                    .map(([name, imp]) => (
                                        <li key={name} className="flex items-center text-[var(--text)]">
                                            <span className="w-16 font-mono text-xs text-[var(--muted)]">{name}</span>
                                            <div className="flex-1 h-3 bg-[var(--bg)] rounded-full ml-2 overflow-hidden border border-[var(--border)]">
                                                <div
                                                    className="h-full bg-[var(--primary)]"
                                                    style={{ width: `${imp * 100}%` }}
                                                ></div>
                                            </div>
                                            <span className="ml-2 text-xs text-[var(--text)]">{(imp * 100).toFixed(1)}%</span>
                                        </li>
                                    ))}
                            </ul>
                        </div>
                    </div>

                    {/* Tree Visualization */}
                    <div className="card h-[600px] flex flex-col">
                        <h2 className="text-xl font-semibold mb-4 border-b border-[var(--border)] pb-2 text-[var(--text)]">Decision Tree Visualization (Estimator 0)</h2>
                        <div className="flex-1 border border-[var(--border)] rounded bg-[var(--bg)] overflow-hidden" style={{ minHeight: '500px' }}>
                            {result.tree_structure && (
                                <Tree
                                    data={result.tree_structure}
                                    orientation="vertical"
                                    translate={{ x: 300, y: 50 }}
                                    pathFunc="step"
                                    separation={{ siblings: 1.5, nonSiblings: 2 }}
                                    zoomable={true}
                                    renderCustomNodeElement={renderCustomNodeElement}
                                />
                            )}
                        </div>
                        <p className="text-xs text-[var(--muted)] mt-2 text-center">
                            Scroll to zoom • Drag to pan • Click nodes to expand/collapse
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
};
