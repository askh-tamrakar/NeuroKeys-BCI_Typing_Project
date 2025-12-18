import React, { useState, useEffect } from 'react'
import Sidebar from '../ui/Sidebar'
import LiveView from '../views/LiveView'
import { ConfigService } from '../../Services/ConfigService'

export default function LiveDashboard({ wsData, wsConfig, wsEvent, sendMessage }) {
    const [config, setConfig] = useState()
    const [isPaused, setIsPaused] = useState(false)
    const [loading, setLoading] = useState(true)

    // Load config on mount
    useEffect(() => {
        ConfigService.loadConfig().then(cfg => {
            setConfig(cfg)
            setLoading(false)
        })
    }, [])

    // Sync incoming config from WebSocket
    useEffect(() => {
        if (wsConfig) {
            console.log("LiveDashboard: Syncing config from WS", wsConfig)

            // Check if it's actually different to avoid unnecessary resets
            // But config is an object, so simple reference check might pass if it's the same object (unlikely from WS)
            // We'll trust the logic for now but log it

            setConfig(wsConfig)

            // Only update local storage to keep them in sync, DO NOT push back to API (causes loop)
            localStorage.setItem('biosignals-config', JSON.stringify(wsConfig))
        }
    }, [wsConfig])

    // Auto-save removed. Manual save only.
    const handleManualSave = () => {
        if (!config) return

        // Persist locally + Backend
        ConfigService.saveConfig(config)

        // Sync to Backend via WS
        if (sendMessage) {
            sendMessage({
                type: 'SAVE_CONFIG',
                config: config
            })
        }
        // alert("Configuration saved and synced!")
    }

    if (loading) return <div className="flex items-center justify-center h-screen bg-bg text-text">Loading Config...</div>

    return (
        <div className="flex h-screen w-full bg-bg overflow-hidden relative">
            {/* Fixed Sidebar */}
            <Sidebar
                config={config}
                setConfig={setConfig}
                isPaused={isPaused}
                setIsPaused={setIsPaused}
                onSave={handleManualSave}
                className="shrink-0 z-20"
            />

            {/* Main Content Area */}
            <main className="flex-grow h-full overflow-hidden relative flex flex-col">
                {/* Header / Top Bar if needed, currently sidebar handles controls */}

                {/* LiveView Visualization */}
                <div className="flex-grow p-4 md:p-6 overflow-hidden relative">
                    <LiveView
                        wsData={wsData}
                        wsEvent={wsEvent}
                        config={config}
                        isPaused={isPaused}
                    />
                </div>
            </main>
        </div>
    )
}
