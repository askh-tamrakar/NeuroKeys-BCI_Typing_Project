import { motion, useSpring, useTransform } from 'motion/react';
import { useEffect } from 'react';

const OPACITY_FACTOR = 1.5; // Controls how fast it fades. Higher = sharper fade.

function Number({ mv, number, height, className, style }) {
    let styleParams = useTransform(mv, latest => {
        let placeValue = latest % 10;
        let offset = (10 + number - placeValue) % 10;

        let memo = offset * height;
        if (offset > 5) {
            memo -= 10 * height;
        }

        // Calculate opacity based on distance from center (0)
        // offset is 0 for current, 1 for next, 9 (aka -1) for prev
        let dist = Math.min(offset, 10 - offset);

        // Linear fade: 1 at dist=0, 0 at dist=1
        // Clamp between 0 and 1
        let opacity = Math.max(0, 1 - (dist * OPACITY_FACTOR));

        return { y: memo, opacity };
    });

    return (
        <motion.span
            className={className}
            style={{
                ...style,
                y: useTransform(styleParams, s => s.y),
                opacity: useTransform(styleParams, s => s.opacity),
                position: 'absolute',
                display: 'block'
            }}
        >
            {number}
        </motion.span>
    );
}

function Digit({ place, value, height, className, style }) {
    let valueRoundedToPlace = Math.floor(value / place);
    let animatedValue = useSpring(valueRoundedToPlace);
    useEffect(() => {
        animatedValue.set(valueRoundedToPlace);
    }, [animatedValue, valueRoundedToPlace]);
    return (
        <div style={{ height, position: 'relative', width: '1ch', overflow: 'hidden', display: 'inline-block' }}>
            {Array.from({ length: 10 }, (_, i) => (
                <Number key={i} mv={animatedValue} number={i} height={height} className={className} style={style} />
            ))}
        </div>
    );
}

export default function Counter({
    value,
    fontSize = 100,
    places = [100, 10, 1],
    className,
    style
}) {
    return (
        <div style={{ fontSize, display: 'flex', ...style }} className={className}>
            {places.map(place => (
                <Digit key={place} place={place} value={value} height={fontSize} />
            ))}
        </div>
    );
}
