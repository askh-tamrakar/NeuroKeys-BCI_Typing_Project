import React, { useState, useEffect } from 'react'
import Sidebar from '../ui/Sidebar'
import LiveView from '../views/LiveView'
import { ConfigService } from '../../Services/ConfigService'

export default function LiveDashboard({ wsData, sendMessage }) {
    const [config, setConfig] = useState()
    const [isPaused, setIsPaused] = useState(false)
    const [loading, setLoading] = useState(true)

    // Load config on mount
    useEffect(() => {
        ConfigService.loadConfig().then(cfg => {
            setConfig(cfg)
            setLoading(false)
        })

        const handleConfigChanged = (e) => {
            console.log('Config changed from other source, reloading...')
            setConfig(e.detail)
        }

        window.addEventListener('config-changed', handleConfigChanged)
        return () => window.removeEventListener('config-changed', handleConfigChanged)
    }, [])

    const handleSaveMapping = async (updatedConfig) => {
        try {
            // Save to localStorage first (instant)
            await ConfigService.saveConfig(updatedConfig)

            // Broadcast to backend via WebSocket
            if (sendMessage) {
                const result = sendMessage({
                    type: 'SAVE_CONFIG',
                    config: updatedConfig
                })
                if (!result) {
                    console.warn('WebSocket not connected, but localStorage saved')
                }
            }

            return true
        } catch (error) {
            console.error('Save failed:', error)
            return false
        }
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
                onSaveMapping={handleSaveMapping}
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
