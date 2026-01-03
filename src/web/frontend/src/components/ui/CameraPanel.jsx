import React, { useEffect, useRef, useState, useCallback } from 'react';
// Imports
import { Camera, CameraOff, SwitchCamera, ZoomIn } from 'lucide-react';
import '../../styles/ui/CameraPanel.css';

const CameraPanel = () => {
    const videoRef = useRef(null);
    const [error, setError] = useState(null);
    const [devices, setDevices] = useState([]);
    const [currentDeviceIndex, setCurrentDeviceIndex] = useState(0);
    const [isCameraOn, setIsCameraOn] = useState(true);
    const [zoom, setZoom] = useState(1);

    // Enumerate devices on mount
    useEffect(() => {
        const getDevices = async () => {
            try {
                const devs = await navigator.mediaDevices.enumerateDevices();
                const videoDevices = devs.filter(device => device.kind === 'videoinput');
                setDevices(videoDevices);
            } catch (err) {
                console.error("Error listing devices:", err);
            }
        };
        getDevices();
    }, []);

    // Start/Stop camera stream
    useEffect(() => {
        let stream = null;

        const startCamera = async () => {
            if (!isCameraOn) {
                if (videoRef.current) {
                    videoRef.current.srcObject = null;
                }
                return;
            }

            if (devices.length === 0) return; // Wait for devices

            try {
                // Stop any previous stream tracks
                if (videoRef.current && videoRef.current.srcObject) {
                    videoRef.current.srcObject.getTracks().forEach(track => track.stop());
                }

                const deviceId = devices[currentDeviceIndex]?.deviceId;

                stream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        deviceId: deviceId ? { exact: deviceId } : undefined,
                        width: { ideal: 320 },
                        height: { ideal: 240 },
                        frameRate: { ideal: 30 }
                    },
                    audio: false
                });

                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                }
                setError(null);
            } catch (err) {
                console.error("Error accessing camera:", err);
                setError("Camera access error");
            }
        };

        startCamera();

        return () => {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
        };
    }, [currentDeviceIndex, devices, isCameraOn]);

    const handleSwitchCamera = useCallback(() => {
        if (devices.length > 1) {
            setCurrentDeviceIndex(prev => (prev + 1) % devices.length);
        }
    }, [devices]);

    const toggleCamera = useCallback(() => {
        setIsCameraOn(prev => !prev);
    }, []);

    if (error) {
        return (
            <div className="card bg-surface border border-border shadow-card rounded-2xl p-4 flex items-center justify-center min-h-[200px]">
                <span className="text-red-500 text-sm">{error}</span>
            </div>
        )
    }

    return (
        <div className="camera-panel-card card group">
            {/* Header/Label */}
            <div className="camera-label">
                <h3 className="text-sm font-bold text-text uppercase tracking-wider flex items-center gap-2"><Camera size={16} /> Camera Feed</h3>
            </div>

            {/* Controls Container */}
            <div className="camera-controls">
                {/* Switch Button (Visible if multiple devices) */}
                {devices.length > 1 && isCameraOn && (
                    <button
                        onClick={handleSwitchCamera}
                        className="camera-btn switch"
                        title="Switch Camera"
                    >
                        <SwitchCamera size={16} />
                    </button>
                )}

                {/* On/Off Toggle */}
                <button
                    onClick={toggleCamera}
                    className={`camera-btn toggle ${!isCameraOn ? 'off' : ''}`}
                    title={isCameraOn ? "Turn Camera Off" : "Turn Camera On"}
                >
                    {isCameraOn ? <Camera size={16} /> : <CameraOff size={16} />}
                </button>
            </div>

            {/* Video or Placeholder */}
            {isCameraOn ? (
                <div className="relative overflow-hidden rounded-[10px] border border-border" style={{ aspectRatio: '16/9' }}>
                    <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted
                        className="w-full h-full object-cover bg-black"
                        style={{ transform: `scaleX(-1) scale(${zoom})`, transformOrigin: 'center center' }}
                    />
                </div>
            ) : (
                <div className="camera-placeholder">
                    <CameraOff size={32} className="text-muted opacity-20" />
                    <span className="text-xs text-muted font-mono mt-2 uppercase tracking-widest">Camera Off</span>
                </div>
            )}

            {/* Zoom Control */}
            {isCameraOn && (
                <div className="flex items-center gap-2 mt-3 px-1">
                    <ZoomIn size={16} className="text-muted" />
                    <input
                        type="range"
                        min="1"
                        max="3"
                        step="0.1"
                        value={zoom}
                        onChange={(e) => setZoom(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-border rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                </div>
            )}
        </div>
    );
};

// Check for equality to prevent re-renders if parent re-renders
export default React.memo(CameraPanel, () => true);
