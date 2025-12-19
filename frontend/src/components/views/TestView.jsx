
import React, { useState, useRef, useCallback, useMemo } from 'react';
import '../../styles/CalibrationPage.css';


// ============================================================================
// SENSOR CONFIGURATION & CONSTANTS
// ============================================================================


const SENSOR_TYPES = {
    EMG: {
        name: 'EMG',
        actions: ['ROCK', 'PAPER', 'SCISSOR', 'REST'],
        features: ['mav', 'rms', 'var', 'wl', 'peak', 'range', 'energy', 'entropy', 'iemg', 'zcr'],
    },
    EOG: {
        name: 'EOG',
        actions: ['BLINK', 'REST'],
        features: ['amp_threshold', 'min_duration_ms', 'max_duration_ms', 'min_asymmetry', 'max_asymmetry', 'min_kurtosis'],
    },
    EEG: {
        name: 'EEG',
        actions: ['8Hz', '12Hz', '15Hz', 'REST'],
        features: ['amp_threshold', 'freq_bands'],
    },
};


const MODE = {
    REALTIME: 'REALTIME',
    RECORDING: 'RECORDING',
};


const WINDOW_STATUS = {
    CORRECT: 'CORRECT',
    MISSED: 'MISSED',
};


// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================


/**
 * Generate dummy signal data for graph visualization
 * @param {number} startTime - ms
 * @param {number} endTime - ms
 * @param {string} sensorType - EMG, EOG, EEG
 * @returns {Array<{time: number, value: number}>}
 */
const generateDummySignal = (startTime, endTime, sensorType) => {
    const points = [];
    const samplingRate = 512;
    const duration = (endTime - startTime) / 1000;
    const numSamples = Math.ceil(duration * samplingRate);


    for (let i = 0; i < numSamples; i++) {
        const time = startTime + (i / samplingRate) * 1000;
        let value;


        if (sensorType === 'EMG') {
            value = Math.random() * 100 + 50 * Math.sin(i / 20);
        } else if (sensorType === 'EOG') {
            value = Math.random() * 10 + 5 * Math.sin(i / 10);
        } else if (sensorType === 'EEG') {
            value = Math.random() * 20 + 15 * Math.sin(i / 30);
        }


        points.push({ time, value });
    }


    return points;
};


/**
 * Format timestamp as HH:MM:SS
 */
const formatTime = (ms) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    return `${String(hours).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
};


/**
 * Format date for filename
 */
const formatDateForFilename = () => {
    const now = new Date();
    const dd = String(now.getDate()).padStart(2, '0');
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const yyyy = now.getFullYear();
    const hh = String(now.getHours()).padStart(2, '0');
    const min = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    return `${dd}-${mm}-${yyyy}__${hh}-${min}-${ss}`;
};


/**
 * Extract sensor-specific config from sensor_config.json
 * @param {Object} fullConfig - Complete sensor_config.json
 * @param {string} sensorType - EMG | EOG | EEG
 * @returns {Object} Sensor-specific features/config
 */
const extractSensorConfig = (fullConfig, sensorType) => {
    if (!fullConfig || !fullConfig.features) return {};
    return fullConfig.features[sensorType] || {};
};


// ============================================================================
// LIVE GRAPH COMPONENT - REUSABLE FOR BOTH MODES
// ============================================================================


/**
 * LiveGraph - Displays sensor signal with zoom/pan capabilities
 * @param {Object} props
 * @param {Array<{time: number, value: number}>} props.data - Signal data points
 * @param {number} props.startTime - Start time of view (ms)
 * @param {number} props.endTime - End time of view (ms)
 * @param {Function} props.onViewChange - Callback when view window changes
 * @param {Function} props.onSelectWindow - Callback when window is selected (recording mode)
 * @param {Array<Object>} props.highlights - Array of {startTime, endTime, label, status} for marking windows
 * @param {string} props.mode - REALTIME or RECORDING
 * @param {boolean} props.isSelecting - Is user in selection mode
 * @param {string} props.sensorType - EMG, EOG, EEG
 */
const LiveGraph = ({
    data = [],
    startTime = 0,
    endTime = 12000,
    onViewChange,
    onSelectWindow,
    highlights = [],
    mode = MODE.REALTIME,
    isSelecting = false,
    sensorType = 'EMG',
}) => {
    const canvasRef = useRef(null);
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState(null);
    const [selectionStart, setSelectionStart] = useState(null);
    const [selectionEnd, setSelectionEnd] = useState(null);


    const canvasWidth = 800;
    const canvasHeight = 300;
    const padding = 40;


    // Draw the graph
    const drawGraph = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;


        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvasWidth, canvasHeight);


        // Draw background
        ctx.fillStyle = '#f8f9fa';
        ctx.fillRect(0, 0, canvasWidth, canvasHeight);


        // Draw grid
        ctx.strokeStyle = '#e0e0e0';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 10; i++) {
            const y = padding + (i * (canvasHeight - 2 * padding)) / 10;
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(canvasWidth - padding, y);
            ctx.stroke();
        }


        // Draw axis labels
        ctx.fillStyle = '#666';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(formatTime(startTime), padding - 5, canvasHeight - 10);
        ctx.textAlign = 'left';
        ctx.fillText(formatTime(endTime), canvasWidth - padding + 5, canvasHeight - 10);


        // Filter data within view
        const visibleData = data.filter((p) => p.time >= startTime && p.time <= endTime);


        if (visibleData.length > 0) {
            // Find min/max for scaling
            const values = visibleData.map((p) => p.value);
            const minVal = Math.min(...values);
            const maxVal = Math.max(...values);
            const range = maxVal - minVal || 1;


            // Draw signal line
            ctx.strokeStyle = '#2196F3';
            ctx.lineWidth = 2;
            ctx.beginPath();


            visibleData.forEach((point, idx) => {
                const x = padding + ((point.time - startTime) / (endTime - startTime)) * (canvasWidth - 2 * padding);
                const y = canvasHeight - padding - ((point.value - minVal) / range) * (canvasHeight - 2 * padding);


                if (idx === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });


            ctx.stroke();
        }


        // Draw highlights (action windows, blinks, etc.)
        highlights.forEach((hl) => {
            if (hl.startTime < endTime && hl.endTime > startTime) {
                const x1 = padding + Math.max(0, (hl.startTime - startTime) / (endTime - startTime)) * (canvasWidth - 2 * padding);
                const x2 = padding + Math.min(1, (hl.endTime - startTime) / (endTime - startTime)) * (canvasWidth - 2 * padding);


                const isCorrect = hl.status === WINDOW_STATUS.CORRECT;
                ctx.fillStyle = isCorrect ? 'rgba(76, 175, 80, 0.2)' : 'rgba(244, 67, 54, 0.2)';
                ctx.fillRect(x1, 0, x2 - x1, canvasHeight);


                // Draw label
                ctx.fillStyle = isCorrect ? '#4CAF50' : '#F44336';
                ctx.font = 'bold 12px sans-serif';
                ctx.fillText(hl.label, (x1 + x2) / 2 - 20, 20);
            }
        });


        // Draw selection window (recording mode)
        if (selectionStart !== null && selectionEnd !== null) {
            const x1 = padding + ((selectionStart - startTime) / (endTime - startTime)) * (canvasWidth - 2 * padding);
            const x2 = padding + ((selectionEnd - startTime) / (endTime - startTime)) * (canvasWidth - 2 * padding);


            ctx.fillStyle = 'rgba(255, 193, 7, 0.3)';
            ctx.fillRect(Math.min(x1, x2), 0, Math.abs(x2 - x1), canvasHeight);


            ctx.strokeStyle = '#FFC107';
            ctx.lineWidth = 2;
            ctx.strokeRect(Math.min(x1, x2), 0, Math.abs(x2 - x1), canvasHeight);
        }


        // Draw axes
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding, padding);
        ctx.lineTo(padding, canvasHeight - padding);
        ctx.lineTo(canvasWidth - padding, canvasHeight - padding);
        ctx.stroke();
    }, [startTime, endTime, data, highlights, selectionStart, selectionEnd, canvasWidth, canvasHeight, padding]);


    // Redraw on mount and when dependencies change
    React.useEffect(() => {
        drawGraph();
    }, [drawGraph]);


    // Handle mouse wheel zoom
    const handleWheel = (e) => {
        e.preventDefault();
        const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
        const duration = endTime - startTime;
        const newDuration = duration * zoomFactor;
        const center = startTime + duration / 2;


        const newStart = center - newDuration / 2;
        const newEnd = center + newDuration / 2;


        onViewChange?.({ startTime: Math.max(0, newStart), endTime: newEnd });
    };


    // Handle pan (click and drag)
    const handleMouseDown = (e) => {
        const rect = canvasRef.current.getBoundingClientRect();
        const mouseX = (e.clientX - rect.left - padding) / (canvasWidth - 2 * padding);


        if (isSelecting && mode === MODE.RECORDING) {
            // Recording mode: start selection
            const clickedTime = startTime + mouseX * (endTime - startTime);
            setSelectionStart(clickedTime);
            setSelectionEnd(clickedTime);
        } else {
            // Pan mode
            setIsDragging(true);
            setDragStart(mouseX);
        }
    };


    const handleMouseMove = (e) => {
        if (!isSelecting && isDragging && dragStart !== null) {
            const rect = canvasRef.current.getBoundingClientRect();
            const mouseX = (e.clientX - rect.left - padding) / (canvasWidth - 2 * padding);
            const delta = (dragStart - mouseX) * (endTime - startTime);


            onViewChange?.({ startTime: startTime + delta, endTime: endTime + delta });
            setDragStart(mouseX);
        } else if (isSelecting && mode === MODE.RECORDING && selectionStart !== null) {
            // Recording mode: extend selection
            const rect = canvasRef.current.getBoundingClientRect();
            const mouseX = (e.clientX - rect.left - padding) / (canvasWidth - 2 * padding);
            const currentTime = startTime + mouseX * (endTime - startTime);
            setSelectionEnd(currentTime);
            drawGraph();
        }
    };


    const handleMouseUp = () => {
        if (isSelecting && selectionStart !== null && selectionEnd !== null) {
            onSelectWindow?.({
                startTime: Math.min(selectionStart, selectionEnd),
                endTime: Math.max(selectionStart, selectionEnd),
            });
            setSelectionStart(null);
            setSelectionEnd(null);
        }
        setIsDragging(false);
        setDragStart(null);
    };


    return (
        <div className="live-graph">
            <canvas
                ref={canvasRef}
                width={canvasWidth}
                height={canvasHeight}
                onWheel={handleWheel}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                style={{ cursor: isSelecting ? 'crosshair' : 'grab' }}
            />
            <div className="graph-controls">
                <button
                    onClick={() => {
                        const duration = endTime - startTime;
                        const center = startTime + duration / 2;
                        onViewChange?.({
                            startTime: Math.max(0, center - duration / 4),
                            endTime: center + duration / 4,
                        });
                    }}
                >
                    🔍 Zoom In
                </button>
                <button
                    onClick={() => {
                        const duration = endTime - startTime;
                        const center = startTime + duration / 2;
                        onViewChange?.({ startTime: center - duration, endTime: center + duration });
                    }}
                >
                    🔍 Zoom Out
                </button>
                <button onClick={() => onViewChange?.({ startTime: 0, endTime: 12000 })}>
                    Reset View
                </button>
            </div>
        </div>
    );
};


// ============================================================================
// MODE TOGGLE COMPONENT
// ============================================================================


const ModeToggle = ({ mode, onModeChange }) => {
    return (
        <div className="mode-toggle">
            <label>
                <input
                    type="radio"
                    value={MODE.REALTIME}
                    checked={mode === MODE.REALTIME}
                    onChange={(e) => onModeChange(e.target.value)}
                />
                Realtime Calibration
            </label>
            <label>
                <input
                    type="radio"
                    value={MODE.RECORDING}
                    checked={mode === MODE.RECORDING}
                    onChange={(e) => onModeChange(e.target.value)}
                />
                Recording Calibration
            </label>
        </div>
    );
};


// ============================================================================
// REALTIME CALIBRATION CONTROLS
// ============================================================================


const RealtimeControls = ({
    sensorType,
    currentAction,
    onActionChange,
    windowLength,
    onWindowLengthChange,
    windowOverlap,
    onWindowOverlapChange,
    onStartRecording,
    onStopRecording,
    isRecording,
    windows,
    onWindowStatusChange,
}) => {
    const actions = SENSOR_TYPES[sensorType].actions;


    return (
        <div className="realtime-controls">
            <div className="control-section">
                <label>Current Action:</label>
                <select value={currentAction} onChange={(e) => onActionChange(e.target.value)}>
                    {actions.map((action) => (
                        <option key={action} value={action}>
                            {action}
                        </option>
                    ))}
                </select>
            </div>


            <div className="control-section">
                <label>Window Length (ms):</label>
                <input
                    type="number"
                    min="100"
                    step="100"
                    value={windowLength}
                    onChange={(e) => onWindowLengthChange(Number(e.target.value))}
                />
            </div>


            <div className="control-section">
                <label>Window Overlap (%):</label>
                <input
                    type="range"
                    min="0"
                    max="50"
                    step="5"
                    value={windowOverlap}
                    onChange={(e) => onWindowOverlapChange(Number(e.target.value))}
                />
                <span>{windowOverlap}%</span>
            </div>


            <div className="control-section">
                <button
                    className={`btn btn-${isRecording ? 'danger' : 'primary'}`}
                    onClick={isRecording ? onStopRecording : onStartRecording}
                >
                    {isRecording ? 'Stop Recording' : 'Start Recording'}
                </button>
            </div>


            {/* Windows List */}
            <div className="windows-list">
                <h4>Calibration Windows</h4>
                {windows.length === 0 ? (
                    <p className="empty-state">No windows yet. Start recording to create windows.</p>
                ) : (
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Action</th>
                                <th>Time Range</th>
                                <th>Status</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {windows.map((w, idx) => (
                                <tr key={idx}>
                                    <td>{idx + 1}</td>
                                    <td>{w.action}</td>
                                    <td>
                                        {formatTime(w.startTime)} - {formatTime(w.endTime)}
                                    </td>
                                    <td>{w.status}</td>
                                    <td>
                                        <button
                                            className="btn-small"
                                            onClick={() =>
                                                onWindowStatusChange(idx, w.status === WINDOW_STATUS.CORRECT ? WINDOW_STATUS.MISSED : WINDOW_STATUS.CORRECT)
                                            }
                                        >
                                            Toggle
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};


// ============================================================================
// RECORDING CALIBRATION CONTROLS
// ============================================================================


const RecordingControls = ({ windows, onWindowStatusChange, onDeleteWindow, onCalibrateFromRecording }) => {
    return (
        <div className="recording-controls">
            {/* Annotations List */}
            <div className="annotations-list">
                <h4>Annotated Windows</h4>
                {windows.length === 0 ? (
                    <p className="empty-state">No annotations yet. Click and drag on the graph to create windows.</p>
                ) : (
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Tag</th>
                                <th>Time Range</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {windows.map((w, idx) => (
                                <tr key={idx}>
                                    <td>{idx + 1}</td>
                                    <td>{w.tag}</td>
                                    <td>
                                        {formatTime(w.startTime)} - {formatTime(w.endTime)}
                                    </td>
                                    <td>{w.status}</td>
                                    <td>
                                        <button
                                            className="btn-small"
                                            onClick={() =>
                                                onWindowStatusChange(idx, w.status === WINDOW_STATUS.CORRECT ? WINDOW_STATUS.MISSED : WINDOW_STATUS.CORRECT)
                                            }
                                        >
                                            Toggle
                                        </button>
                                        <button className="btn-small btn-danger" onClick={() => onDeleteWindow(idx)}>
                                            Delete
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>


            <button className="btn btn-success" onClick={onCalibrateFromRecording}>
                Calibrate from Annotations
            </button>
        </div>
    );
};


// ============================================================================
// ANNOTATION DIALOG (for recording mode window selection)
// ============================================================================


const AnnotationDialog = ({ isOpen, sensorType, onConfirm, onCancel }) => {
    const [selectedTag, setSelectedTag] = useState('');
    const actions = SENSOR_TYPES[sensorType]?.actions || [];


    if (!isOpen) return null;


    return (
        <div className="dialog-overlay">
            <div className="dialog">
                <h3>Tag Window</h3>
                <label>
                    Select action:
                    <select value={selectedTag} onChange={(e) => setSelectedTag(e.target.value)}>
                        <option value="">-- Choose --</option>
                        {actions.map((action) => (
                            <option key={action} value={action}>
                                {action}
                            </option>
                        ))}
                    </select>
                </label>
                <div className="dialog-actions">
                    <button onClick={onCancel} className="btn btn-secondary">
                        Cancel
                    </button>
                    <button
                        onClick={() => {
                            if (selectedTag) onConfirm(selectedTag);
                        }}
                        className="btn btn-primary"
                        disabled={!selectedTag}
                    >
                        Confirm
                    </button>
                </div>
            </div>
        </div>
    );
};


// ============================================================================
// CALIBRATION CONFIG PANEL
// ============================================================================


const CalibrationConfigPanel = ({ sensorType, fullConfig, currentConfig, previewConfig, onApplyCalibration, onRevertCalibration, onLoadConfig }) => {
    const handleConfigFileLoad = (file) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const config = JSON.parse(e.target.result);
                onLoadConfig?.(config);
            } catch (error) {
                alert('Error parsing JSON file: ' + error.message);
            }
        };
        reader.readAsText(file);
    };


    return (
        <div className="config-panel">
            <h3>Calibration Configuration</h3>


            <div className="control-section">
                <label>Load sensor_config.json:</label>
                <input
                    type="file"
                    accept=".json"
                    onChange={(e) => e.target.files && handleConfigFileLoad(e.target.files[0])}
                />
            </div>


            <div className="config-section">
                <h4>Current Values</h4>
                {Object.keys(currentConfig).length === 0 ? (
                    <p className="empty-state">No configuration loaded. Upload sensor_config.json to begin.</p>
                ) : (
                    <div className="json-viewer">
                        <pre>{JSON.stringify(currentConfig, null, 2)}</pre>
                    </div>
                )}
            </div>


            {previewConfig && Object.keys(previewConfig).length > 0 && (
                <div className="config-section">
                    <h4>Preview (New Values)</h4>
                    <div className="json-viewer">
                        <pre>{JSON.stringify(previewConfig, null, 2)}</pre>
                    </div>
                </div>
            )}


            <div className="config-actions">
                <button
                    className="btn btn-success"
                    onClick={() => onApplyCalibration(sensorType)}
                    disabled={!previewConfig || Object.keys(previewConfig).length === 0}
                >
                    Apply Calibration
                </button>
                <button
                    className="btn btn-secondary"
                    onClick={() => onRevertCalibration(sensorType)}
                    disabled={!previewConfig || Object.keys(previewConfig).length === 0}
                >
                    Revert
                </button>
            </div>
        </div>
    );
};


// ============================================================================
// MAIN CALIBRATION PAGE
// ============================================================================


export default function CalibrationPage({ onCalibrateCallback, onRecordingCallback, onLoadRecordingCallback }) {
    const [selectedSensor, setSelectedSensor] = useState('EMG');
    const [mode, setMode] = useState(MODE.REALTIME);


    // Realtime state
    const [currentAction, setCurrentAction] = useState('ROCK');
    const [windowLength, setWindowLength] = useState(2000);
    const [windowOverlap, setWindowOverlap] = useState(10);
    const [isRecording, setIsRecording] = useState(false);
    const [realtimeWindows, setRealtimeWindows] = useState([]);


    // Recording state
    const [recordingData, setRecordingData] = useState([]);
    const [recordingWindows, setRecordingWindows] = useState([]);
    const [loadedFileName, setLoadedFileName] = useState('');
    const [recordingStartTime, setRecordingStartTime] = useState(0);
    const [recordingEndTime, setRecordingEndTime] = useState(12000);
    const [annotationDialogOpen, setAnnotationDialogOpen] = useState(false);


    // Graph state
    const [graphStartTime, setGraphStartTime] = useState(0);
    const [graphEndTime, setGraphEndTime] = useState(12000);
    const [isSelectingWindow, setIsSelectingWindow] = useState(false);


    // Config state
    const [fullConfig, setFullConfig] = useState({});
    const [currentConfig, setCurrentConfig] = useState({});
    const [previewConfig, setPreviewConfig] = useState(null);


    // Initialize graph data
    const graphData = useMemo(() => {
        if (mode === MODE.REALTIME) {
            return generateDummySignal(graphStartTime, graphEndTime, selectedSensor);
        } else {
            return recordingData.length > 0
                ? recordingData.filter((p) => p.time >= graphStartTime && p.time <= graphEndTime)
                : generateDummySignal(graphStartTime, graphEndTime, selectedSensor);
        }
    }, [graphStartTime, graphEndTime, selectedSensor, mode, recordingData]);


    // Highlights for graph
    const graphHighlights = useMemo(() => {
        const windows = mode === MODE.REALTIME ? realtimeWindows : recordingWindows;
        return windows.map((w) => ({
            startTime: w.startTime,
            endTime: w.endTime,
            label: w.action || w.tag,
            status: w.status || WINDOW_STATUS.CORRECT,
        }));
    }, [mode, realtimeWindows, recordingWindows]);


    // Update current config when sensor or config changes
    React.useEffect(() => {
        const sensorConfig = extractSensorConfig(fullConfig, selectedSensor);
        setCurrentConfig(sensorConfig);
    }, [fullConfig, selectedSensor]);


    // Handlers
    const handleViewChange = ({ startTime, endTime }) => {
        setGraphStartTime(startTime);
        setGraphEndTime(endTime);
    };


    const handleStartRecording = () => {
        setIsRecording(true);
        setRealtimeWindows([]);
        onRecordingCallback?.({ action: 'start', sensorType: selectedSensor });
    };


    const handleStopRecording = () => {
        setIsRecording(false);
        const filename = `${selectedSensor}-${formatDateForFilename()}.csv`;
        onRecordingCallback?.({ action: 'stop', sensorType: selectedSensor, filename });
    };


    const handleLoadRecording = (file) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const content = e.target.result;
            const lines = content.split('\n');
            const data = [];
            lines.forEach((line, idx) => {
                const value = parseFloat(line);
                if (!isNaN(value)) {
                    data.push({ time: idx * 2, value });
                }
            });
            setRecordingData(data);
            setLoadedFileName(file.name);
            if (data.length > 0) {
                setRecordingEndTime(data[data.length - 1].time);
            }
            setRecordingWindows([]);
        };
        reader.readAsText(file);
    };


    const handleLoadConfig = (config) => {
        setFullConfig(config);
        const sensorConfig = extractSensorConfig(config, selectedSensor);
        setCurrentConfig(sensorConfig);
        alert(`Configuration loaded successfully for ${selectedSensor}`);
    };


    const handleSelectWindowInRecording = ({ startTime, endTime }) => {
        setAnnotationDialogOpen(true);
        setIsSelectingWindow(false);
    };


    const handleConfirmAnnotation = (tag) => {
        const newWindow = {
            startTime: Math.min(graphStartTime, graphEndTime),
            endTime: Math.max(graphStartTime, graphEndTime),
            tag,
            status: WINDOW_STATUS.CORRECT,
        };
        setRecordingWindows([...recordingWindows, newWindow]);
        setAnnotationDialogOpen(false);
    };


    const handleWindowStatusChange = (idx, newStatus, isRecording = false) => {
        if (isRecording) {
            const updated = [...recordingWindows];
            updated[idx].status = newStatus;
            setRecordingWindows(updated);
        } else {
            const updated = [...realtimeWindows];
            updated[idx].status = newStatus;
            setRealtimeWindows(updated);
        }
    };


    const handleDeleteWindow = (idx) => {
        const updated = recordingWindows.filter((_, i) => i !== idx);
        setRecordingWindows(updated);
    };


    const handleCalibrateFromRecording = () => {
        const calibrationData = {
            sensorType: selectedSensor,
            windows: recordingWindows,
            fileMeta: { fileName: loadedFileName },
        };
        onCalibrateCallback?.(calibrationData);
    };


    const handleApplyCalibration = (sensorType) => {
        if (previewConfig && Object.keys(previewConfig).length > 0) {
            // Update the full config
            const updatedConfig = {
                ...fullConfig,
                features: {
                    ...fullConfig.features,
                    [sensorType]: previewConfig,
                },
            };
            setFullConfig(updatedConfig);
            setCurrentConfig(previewConfig);
            onCalibrateCallback?.({ action: 'apply', sensorType, config: previewConfig });
            setPreviewConfig(null);
        }
    };


    const handleRevertCalibration = (sensorType) => {
        setPreviewConfig(null);
    };


    // Simulate window generation for realtime
    React.useEffect(() => {
        if (isRecording && currentAction !== 'REST' && mode === MODE.REALTIME) {
            const interval = setInterval(() => {
                const now = Date.now();
                const windowStart = now;
                const windowEnd = now + windowLength;
                const overlap = (windowLength * windowOverlap) / 100;


                setRealtimeWindows((prev) => [
                    ...prev,
                    {
                        startTime: windowStart,
                        endTime: windowEnd,
                        action: currentAction,
                        status: WINDOW_STATUS.CORRECT,
                    },
                ]);
            }, windowLength - (windowLength * windowOverlap) / 100);


            return () => clearInterval(interval);
        }
    }, [isRecording, currentAction, windowLength, windowOverlap, mode]);


    return (
        <div className="calibration-page">
            <header className="calibration-header">
                <h1>Biosignal Calibration Tool</h1>
                <p>Calibrate EMG, EOG, and EEG sensors for optimal detection</p>
            </header>


            {/* Sensor Tabs */}
            <div className="sensor-tabs">
                {Object.keys(SENSOR_TYPES).map((sensor) => (
                    <button
                        key={sensor}
                        className={`tab ${selectedSensor === sensor ? 'active' : ''}`}
                        onClick={() => {
                            setSelectedSensor(sensor);
                            setMode(MODE.REALTIME);
                            setCurrentAction(SENSOR_TYPES[sensor].actions[0]);
                        }}
                    >
                        {SENSOR_TYPES[sensor].name}
                    </button>
                ))}
            </div>


            {/* Main Layout */}
            <div className="calibration-container">
                {/* Left: Graph */}
                <div className="graph-section">
                    <h3>{selectedSensor} Signal</h3>
                    <LiveGraph
                        data={graphData}
                        startTime={graphStartTime}
                        endTime={graphEndTime}
                        onViewChange={handleViewChange}
                        onSelectWindow={handleSelectWindowInRecording}
                        highlights={graphHighlights}
                        mode={mode}
                        isSelecting={isSelectingWindow}
                        sensorType={selectedSensor}
                    />
                </div>


                {/* Right: Controls & Config */}
                <div className="control-section">
                    <ModeToggle mode={mode} onModeChange={setMode} />


                    {mode === MODE.REALTIME ? (
                        <RealtimeControls
                            sensorType={selectedSensor}
                            currentAction={currentAction}
                            onActionChange={setCurrentAction}
                            windowLength={windowLength}
                            onWindowLengthChange={setWindowLength}
                            windowOverlap={windowOverlap}
                            onWindowOverlapChange={setWindowOverlap}
                            onStartRecording={handleStartRecording}
                            onStopRecording={handleStopRecording}
                            isRecording={isRecording}
                            windows={realtimeWindows}
                            onWindowStatusChange={(idx, status) => handleWindowStatusChange(idx, status, false)}
                        />
                    ) : (
                        <>
                            <div className="file-section">
                                <h4>Load Recording</h4>
                                <input
                                    type="file"
                                    accept=".csv,.txt"
                                    onChange={(e) => e.target.files && handleLoadRecording(e.target.files[0])}
                                />
                                {loadedFileName && (
                                    <div className="file-info">
                                        <p>
                                            <strong>Loaded:</strong> {loadedFileName}
                                        </p>
                                        <p>
                                            <strong>Duration:</strong> {formatTime(recordingStartTime)} - {formatTime(recordingEndTime)}
                                        </p>
                                    </div>
                                )}
                            </div>


                            <div className="selection-mode">
                                <button
                                    className={`btn ${isSelectingWindow ? 'active' : ''}`}
                                    onClick={() => setIsSelectingWindow(!isSelectingWindow)}
                                >
                                    {isSelectingWindow ? 'Drawing Mode' : 'Click to Draw Windows'}
                                </button>
                            </div>


                            <RecordingControls
                                windows={recordingWindows}
                                onWindowStatusChange={(idx, status) => handleWindowStatusChange(idx, status, true)}
                                onDeleteWindow={handleDeleteWindow}
                                onCalibrateFromRecording={handleCalibrateFromRecording}
                            />
                        </>
                    )}


                    <CalibrationConfigPanel
                        sensorType={selectedSensor}
                        fullConfig={fullConfig}
                        currentConfig={currentConfig}
                        previewConfig={previewConfig}
                        onApplyCalibration={handleApplyCalibration}
                        onRevertCalibration={handleRevertCalibration}
                        onLoadConfig={handleLoadConfig}
                    />
                </div>
            </div>


            {/* Annotation Dialog */}
            <AnnotationDialog
                isOpen={annotationDialogOpen}
                sensorType={selectedSensor}
                onConfirm={handleConfirmAnnotation}
                onCancel={() => setAnnotationDialogOpen(false)}
            />
        </div>
    );
}
