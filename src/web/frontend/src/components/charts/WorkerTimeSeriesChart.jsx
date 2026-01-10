import React, { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';

const WorkerTimeSeriesChart = forwardRef(({
    className,
    config = {},
    timeWindow = 5000,
    activeSensor,
    activeChannelIndex,
    onWindowSelect
}, ref) => {

    const containerRef = useRef(null);
    const canvasRef = useRef(null);
    const workerRef = useRef(null);

    // Selection State
    const isDragging = useRef(false);
    const startX = useRef(0);

    // ID counter for async requests
    const requestIdCounter = useRef(0);
    const pendingRequests = useRef(new Map());

    // Transfer state to prevent double-transfer in StrictMode
    const isTransferred = useRef(false);
    const workerCleanupTimerRef = useRef(null);

    // Initialize Worker
    useEffect(() => {
        if (!canvasRef.current) return;

        // Cancel pending cleanup (Strict Mode "remount")
        if (workerCleanupTimerRef.current) {
            clearTimeout(workerCleanupTimerRef.current);
            workerCleanupTimerRef.current = null;
        }

        if (!workerRef.current) {
            // Check for OffscreenCanvas support
            if (!canvasRef.current.transferControlToOffscreen) {
                console.error("OffscreenCanvas not supported!");
                return;
            }

            try {
                // Create Worker
                const worker = new Worker(new URL('../../workers/chart.worker.js', import.meta.url), { type: 'module' });
                workerRef.current = worker;

                // Transfer Canvas
                // We only transfer if we just created the worker (implying first mount or real remount)
                // If workerRef was null, we assume we need to transfer.
                // BUT wait, isTransferred ref logic from before was to prevent double transfer on SAME instance.
                // Here, if we are in Strict Mode, the component is "remounted".
                // workerRef is a Ref, so it persists?
                // NO, if component is unmounted, Refs ARE discarded if the fiber is killed?
                // React Strict Mode: "Effect cleanup runs, then Effect runs again."
                // Refs ARE preserved during the immediate double-invoke?
                // Actually, in Strict Mode dev, it's: Mount -> Unmount -> Mount.
                // If Unmount happens, refs are usually lost if the component is destroyed.
                // BUT React preserves state for the immediate remount?
                // Let's assume standard behavior:
                // If we don't terminate the worker in cleanup immediately, workerRef.current stays valid?
                // NO, we need to store the worker in a module-level variable or something?
                // No, DinoView uses `workerRef` which is a `useRef`.
                // This implies React preserves the Ref object during the strict mode flicker.

                if (!isTransferred.current) {
                    const offscreen = canvasRef.current.transferControlToOffscreen();
                    isTransferred.current = true;

                    const initPayload = {
                        canvas: offscreen,
                        width: containerRef.current.clientWidth,
                        height: containerRef.current.clientHeight,
                        config: {
                            timeWindow,
                            ...config
                        }
                    };
                    worker.postMessage({ type: 'INIT', payload: initPayload }, [offscreen]);

                    // Handle Responses
                    worker.onmessage = (e) => {
                        const { type, idPromise, payload } = e.data;
                        if (type === 'GET_SAMPLES_RESULT') {
                            if (pendingRequests.current.has(idPromise)) {
                                const resolve = pendingRequests.current.get(idPromise);
                                pendingRequests.current.delete(idPromise);
                                resolve(payload);
                            }
                        } else if (type === 'SELECTION_RESULT') {
                            if (onWindowSelect) {
                                onWindowSelect(payload.start, payload.end);
                            }
                        }
                    };
                }
            } catch (err) {
                console.error("Failed to transfer canvas or init worker:", err);
            }
        } else {
            // Worker already exists (rescued from cleanup)
            // Just update config/resize if needed?
            // It should be running.
            // We might need to re-attach event listeners if we detached them?
            // The onmessage listener is attached to the worker instance.
            // If we reused the worker instance, the old listener is still there?
            // Or we should re-attach it to capture the new 'pendingRequests' closure?
            // YES - we need to re-attach onmessage because 'pendingRequests' ref is stable,
            // but 'onWindowSelect' prop might have changed!
            const worker = workerRef.current;
            worker.onmessage = (e) => {
                const { type, idPromise, payload } = e.data;
                if (type === 'GET_SAMPLES_RESULT') {
                    if (pendingRequests.current.has(idPromise)) {
                        const resolve = pendingRequests.current.get(idPromise);
                        pendingRequests.current.delete(idPromise);
                        resolve(payload);
                    }
                } else if (type === 'SELECTION_RESULT') {
                    if (onWindowSelect) {
                        onWindowSelect(payload.start, payload.end);
                    }
                }
            };
        }

        // Resize Observer
        const observer = new ResizeObserver((entries) => {
            for (let entry of entries) {
                const { width, height } = entry.contentRect;
                if (workerRef.current) {
                    workerRef.current.postMessage({
                        type: 'RESIZE',
                        payload: { width, height }
                    });
                }
            }
        });
        observer.observe(containerRef.current);

        return () => {
            // DELAYED CLEANUP
            workerCleanupTimerRef.current = setTimeout(() => {
                if (workerRef.current) {
                    workerRef.current.terminate();
                    workerRef.current = null;
                }
                observer.disconnect();
                // We can't reset isTransferred since canvas is dead.
            }, 200); // 200ms buffer
        };
    }, [config, timeWindow, onWindowSelect]); // Add deps to ensure listener updates


    const handleMouseDown = (e) => {
        if (!onWindowSelect) return;
        isDragging.current = true;
        const rect = containerRef.current.getBoundingClientRect();
        startX.current = e.clientX - rect.left;
    };

    const handleMouseUp = (e) => {
        if (!isDragging.current) return;
        isDragging.current = false;
        const rect = containerRef.current.getBoundingClientRect();
        const endX = e.clientX - rect.left;

        const dist = Math.abs(endX - startX.current);
        if (dist > 10 && workerRef.current) {
            workerRef.current.postMessage({
                type: 'CALC_SELECTION',
                payload: { x1: startX.current, x2: endX }
            });
        }
    };

    const handleMouseLeave = () => {
        isDragging.current = false;
    };

    // Sync Config Updates
    useEffect(() => {
        if (workerRef.current) {
            workerRef.current.postMessage({
                type: 'SET_CONFIG',
                payload: { timeWindow, ...config }
            });
        }
    }, [config, timeWindow]);

    // Expose API
    useImperativeHandle(ref, () => ({

        addData: (points) => {
            if (workerRef.current) {
                workerRef.current.postMessage({ type: 'ADD_DATA', payload: points });
            }
        },

        updateWindows: (windows) => {
            if (workerRef.current) {
                workerRef.current.postMessage({ type: 'UPDATE_WINDOWS', payload: windows });
            }
        },

        setScanner: (x, value) => {
            if (workerRef.current) {
                workerRef.current.postMessage({ type: 'SET_SCANNER', payload: { x, value } });
            }
        },

        clearData: () => {
            if (workerRef.current) {
                workerRef.current.postMessage({ type: 'CLEAR_DATA' });
            }
        },

        getSamples: (start, end) => {
            return new Promise((resolve) => {
                if (!workerRef.current) {
                    resolve([]);
                    return;
                }
                const id = requestIdCounter.current++;
                pendingRequests.current.set(id, resolve);

                workerRef.current.postMessage({
                    type: 'GET_SAMPLES',
                    idPromise: id,
                    payload: { start, end }
                });
            });
        }

    }));

    return (
        <div
            ref={containerRef}
            className={`w-full h-full relative ${className}`}
            onMouseDown={handleMouseDown}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
        >
            <canvas ref={canvasRef} className="block w-full h-full" />
        </div>
    );
});

export default WorkerTimeSeriesChart;
