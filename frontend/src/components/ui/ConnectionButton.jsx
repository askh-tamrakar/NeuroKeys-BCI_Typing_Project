import { useState } from 'react'
import { Cable, Zap, Plug } from 'lucide-react'
import ElectricBorder from './ElectricBorder.jsx'
import { soundHandler } from '../../handlers/SoundHandler.js'

export function ConnectionButton({ status, latency, connect, disconnect }) {
    const [isConnectingClicked, setIsConnectingClicked] = useState(false)
    const [isSimulatedConnecting, setIsSimulatedConnecting] = useState(false)

    const handleConnectClick = () => {
        soundHandler.playConnectionZap()
        setIsConnectingClicked(true)
        setTimeout(() => setIsConnectingClicked(false), 200)

        if (status === 'connected') {
            disconnect()
        } else {
            setIsSimulatedConnecting(true)
            connect()
            setTimeout(() => {
                setIsSimulatedConnecting(false)
            }, 200)
        }
    }

    const currentDisplayStatus = isSimulatedConnecting ? 'connecting' : status

    const ConnectionIcon = ({ status }) => {
        if (status === 'connected') return <Cable className="w-5 h-5 text-emerald-400" />
        if (status === 'connecting') return <Zap className="w-5 h-5 text-amber-400 animate-pulse" />
        return <Plug className="w-5 h-5 text-red-400" />
    }

    // base width ~18 (small) when not connected, slightly larger when connected
    const widthClass =
        currentDisplayStatus === 'connected'
            ? 'min-w-[9rem]'   // 9rem ≈ 144px (base + +4–6px equivalent)
            : 'min-w-[8.5rem]' // 8.5rem ≈ 136px (connecting/disconnected)

    return (
        <ElectricBorder
            color={
                currentDisplayStatus === 'connected' ? '#10b981' : // Emerald
                    currentDisplayStatus === 'connecting' ? '#f59e0b' : // Amber
                        '#ef4444' // Red
            }
            speed={1.2}
            chaos={0.05}
            thickness={2}
            className={`rounded-full ${widthClass}`}
            style={{ borderRadius: 999 }}
        >
            <button
                onClick={handleConnectClick}
                className={`
        flex items-center justify-center gap-2 px-4 py-2.5 rounded-full border shadow-lg
        font-bold text-sm tracking-wide
        transition-all duration-200 ease-in-out
        w-full h-full
        ${isConnectingClicked ? 'scale-95 shadow-none' : 'scale-100'}
        ${currentDisplayStatus === 'connected'
                        ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/30 shadow-emerald-500/50'
                        : currentDisplayStatus === 'connecting'
                            ? 'bg-amber-500/20 border-amber-500/50 text-amber-400 shadow-amber-500/20'
                            : 'bg-red-500/20 border-red-500/50 text-red-400 hover:bg-red-500/30 shadow-red-500/20'
                    }
      `}
            >
                {/* Left side: icon + text, always centered within the button */}
                <div className="flex items-center gap-2">
                    <ConnectionIcon status={currentDisplayStatus} />
                    <span className="text-sm font-bold uppercase tracking-wider">
                        {currentDisplayStatus === 'connected'
                            ? 'CONNECTED'
                            : currentDisplayStatus === 'connecting'
                                ? 'CONNECTING'
                                : 'DISCONNECTED'}
                    </span>
                </div>

                {/* Right side: latency only when actually connected */}
                {status === 'connected' && (
                    <div className="flex items-center justify-end">
                        <div className="w-[1px] h-4 bg-current opacity-30 mx-1.5" />
                        <span className="text-xs font-mono opacity-80 tabular-nums min-w-[4ch] text-right">
                            {latency}ms
                        </span>
                    </div>
                )}
            </button>
        </ElectricBorder>
    )
}

export default ConnectionButton
