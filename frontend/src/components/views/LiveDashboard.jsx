import React, { useState, useEffect } from 'react'
import Sidebar from '../ui/Sidebar'
import LiveView from '../views/LiveView'
import { ConfigService, DEFAULT_CONFIG } from '../../services/ConfigService'

export default function LiveDashboard({ wsData }) {
    const [config, setConfig] = useState(DEFAULT_CONFIG)
    const [isPaused, setIsPaused] = useState(false)
    const [loading, setLoading] = useState(true)

    // Load config on mount
    useEffect(() => {
        ConfigService.loadConfig().then(cfg => {
            setConfig(cfg)
            setLoading(false)
        })
    }, [])

    // Auto-save config when it changes (debounce could be added)
    useEffect(() => {
        if (!loading) {
            ConfigService.saveConfig(config)
        }
    }, [config, loading])

    if (loading) return <div className="flex items-center justify-center h-screen bg-bg text-text">Loading Config...</div>

    return (
        <div className="flex h-screen w-full bg-bg overflow-hidden relative">
            {/* Fixed Sidebar */}
            <Sidebar
                config={config}
                setConfig={setConfig}
                isPaused={isPaused}
                setIsPaused={setIsPaused}
                className="shrink-0 z-20"
            />

            {/* Main Content Area */}
            <main className="flex-grow h-full overflow-hidden relative flex flex-col">
                {/* Header / Top Bar if needed, currently sidebar handles controls */}

                {/* LiveView Visualization */}
                <div className="flex-grow p-4 md:p-6 overflow-hidden relative">
                    <LiveView
                        wsData={wsData}
                        config={config}
                        isPaused={isPaused}
                    />
                </div>
            </main>
        </div>
    )
}
