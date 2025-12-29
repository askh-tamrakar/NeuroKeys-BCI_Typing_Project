import React, { useEffect, useRef, useState, useCallback } from 'react';

const CameraPanel = () => {
    const videoRef = useRef(null);
    const [error, setError] = useState(null);
    const [devices, setDevices] = useState([]);
    const [currentDeviceIndex, setCurrentDeviceIndex] = useState(0);

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

    // Start camera stream
    useEffect(() => {
        let stream = null;

        const startCamera = async () => {
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
    }, [currentDeviceIndex, devices]);

    const handleSwitchCamera = useCallback(() => {
        if (devices.length > 1) {
            setCurrentDeviceIndex(prev => (prev + 1) % devices.length);
        }
    }, [devices]);

    if (error) {
        return (
            <div className="card bg-surface border border-border shadow-card rounded-2xl p-4 flex items-center justify-center min-h-[200px]">
                <span className="text-red-500 text-sm">{error}</span>
            </div>
        )
    }

    return (
        <div className="card bg-surface border border-border shadow-card rounded-2xl overflow-hidden relative group">
            {/* Header/Label */}
            <div className="absolute top-2 left-3 z-10 bg-black/50 backdrop-blur-sm px-2 py-0.5 rounded text-[10px] text-white font-bold uppercase tracking-wider pointer-events-none">
                Camera Feed
            </div>

            {/* Switch Button (Visible on hover or if multiple devices) */}
            {devices.length > 1 && (
                <button
                    onClick={handleSwitchCamera}
                    className="absolute top-2 right-2 z-20 bg-black/50 hover:bg-primary/80 text-white p-1.5 rounded-full backdrop-blur-sm transition-all opacity-0 group-hover:opacity-100"
                    title="Switch Camera"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
                        <circle cx="12" cy="10" r="3" />
                        <path d="M12 22v-4" />
                        <path d="M8 2h8" />
                    </svg>
                </button>
            )}

            <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-auto object-cover transform -scale-x-100 bg-black"
                style={{ aspectRatio: '4/3' }}
            />
        </div>
    );
};

// Check for equality to prevent re-renders if parent re-renders
export default React.memo(CameraPanel, () => true);
