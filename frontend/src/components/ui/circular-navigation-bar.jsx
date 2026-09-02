import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';

export const ITEM = 44;
export const MARGIN = 20;

const ARCS = {
  'up-left': { mid: 225, sweep: 150 },
  'up-right': { mid: 315, sweep: 150 },
  'down-left': { mid: 135, sweep: 150 },
  'down-right': { mid: 45, sweep: 150 },
  up: { mid: 270, sweep: 160 },
  down: { mid: 90, sweep: 160 },
  left: { mid: 180, sweep: 160 },
  right: { mid: 0, sweep: 160 },
};

function toRad(deg) {
  return (deg * Math.PI) / 180;
}

function directionOrder(cx, cy, vw, vh) {
  const expandLeft = vw - cx <= cx;
  const expandUp = vh - cy <= cy;
  const horizontal = expandLeft ? 'left' : 'right';
  const vertical = expandUp ? 'up' : 'down';
  const preferred = `${vertical}-${horizontal}`;
  const flipH = `${vertical}-${horizontal === 'left' ? 'right' : 'left'}`;
  const flipV = `${vertical === 'up' ? 'down' : 'up'}-${horizontal}`;
  const flipBoth = `${vertical === 'up' ? 'down' : 'up'}-${horizontal === 'left' ? 'right' : 'left'}`;
  const cardinal = expandUp ? ['up', 'down'] : ['down', 'up'];
  const sides = expandLeft ? ['left', 'right'] : ['right', 'left'];
  return [preferred, flipH, flipV, flipBoth, ...cardinal, ...sides];
}

function placeArc(count, radius, midDeg, sweepDeg) {
  const mid = toRad(midDeg);
  const sweep = toRad(sweepDeg);
  const start = mid - sweep / 2;
  return Array.from({ length: count }, (_, index) => {
    const angle = count === 1 ? mid : start + (sweep * index) / Math.max(count - 1, 1);
    return {
      dx: Math.cos(angle) * radius,
      dy: Math.sin(angle) * radius,
      angle,
    };
  });
}

function overflowAmount(spots, cx, cy, vw, vh) {
  let total = 0;
  spots.forEach((spot) => {
    const x = cx + spot.dx;
    const y = cy + spot.dy;
    const left = x - ITEM / 2;
    const right = x + ITEM / 2;
    const top = y - ITEM / 2;
    const bottom = y + ITEM / 2;
    total += Math.max(0, MARGIN - left);
    total += Math.max(0, right - (vw - MARGIN));
    total += Math.max(0, MARGIN - top);
    total += Math.max(0, bottom - (vh - MARGIN));
  });
  return total;
}

function layoutFits(spots, cx, cy, vw, vh) {
  return overflowAmount(spots, cx, cy, vw, vh) === 0;
}

function clampSpots(spots, cx, cy, vw, vh) {
  return spots.map((spot) => {
    let x = cx + spot.dx;
    let y = cy + spot.dy;
    x = Math.min(Math.max(MARGIN + ITEM / 2, x), vw - MARGIN - ITEM / 2);
    y = Math.min(Math.max(MARGIN + ITEM / 2, y), vh - MARGIN - ITEM / 2);
    return { ...spot, dx: x - cx, dy: y - cy };
  });
}

export function layoutFan(count, radius, fabSize, pos, viewport) {
  const vw = viewport.width;
  const vh = viewport.height;
  const cx = pos.x + fabSize / 2;
  const cy = pos.y + fabSize / 2;
  const dirs = directionOrder(cx, cy, vw, vh);
  const sweeps = [150, 120, 90];
  const minRadius = 56;
  let best = null;
  let bestOverflow = Infinity;

  for (const dir of dirs) {
    const arc = ARCS[dir];
    if (!arc) continue;
    for (const sweep of sweeps) {
      for (let scale = radius; scale >= minRadius; scale -= 6) {
        const spots = placeArc(count, scale, arc.mid, sweep);
        if (layoutFits(spots, cx, cy, vw, vh)) return spots;
        const overflow = overflowAmount(spots, cx, cy, vw, vh);
        if (overflow < bestOverflow) {
          bestOverflow = overflow;
          best = spots;
        }
      }
    }
  }

  const fallback = best || placeArc(count, minRadius, ARCS[dirs[0]].mid, 90);
  return clampSpots(fallback, cx, cy, vw, vh);
}

export function placePanel(pos, viewport, fabSize) {
  const vw = viewport.width;
  const vh = viewport.height;
  const gap = 12;
  const phone = vw < 768;
  const fabTop = pos.y;
  const fabBottom = pos.y + fabSize;
  const fabCenterX = pos.x + fabSize / 2;
  const spaceBelow = Math.max(0, vh - fabBottom - gap - MARGIN);
  const spaceAbove = Math.max(0, fabTop - gap - MARGIN);
  const usedWidth = phone ? vw - MARGIN * 2 : Math.min(420, vw - MARGIN * 2);
  const placeBelow = spaceBelow >= 160 || (spaceBelow >= spaceAbove && spaceBelow >= 120);
  const available = placeBelow ? spaceBelow : spaceAbove;
  const maxHeight = Math.max(140, phone ? available : Math.min(available, 560));

  let left;
  let top;
  if (placeBelow) {
    top = fabBottom + gap;
  } else {
    top = MARGIN;
  }

  if (phone) {
    left = MARGIN;
  } else {
    left = fabCenterX - usedWidth / 2;
    left = Math.min(Math.max(MARGIN, left), Math.max(MARGIN, vw - MARGIN - usedWidth));
    const overlapsFab = left < pos.x + fabSize + gap && left + usedWidth > pos.x - gap;
    if (overlapsFab && !placeBelow) {
      const leftSide = pos.x - gap - usedWidth;
      const rightSide = pos.x + fabSize + gap;
      if (leftSide >= MARGIN) left = leftSide;
      else if (rightSide + usedWidth <= vw - MARGIN) left = rightSide;
    }
  }

  left = Math.min(Math.max(MARGIN, left), Math.max(MARGIN, vw - MARGIN - usedWidth));
  top = Math.min(Math.max(MARGIN, top), Math.max(MARGIN, vh - MARGIN - 80));
  return { left, top, width: usedWidth, maxHeight };
}

function captionShift(spot) {
  const angle = Number.isFinite(spot.angle) ? spot.angle : Math.atan2(spot.dy || 0, spot.dx || 1);
  const dist = 36;
  return {
    x: Math.round(Math.cos(angle) * dist),
    y: Math.round(Math.sin(angle) * dist),
  };
}

export default function CircularNavigation({
  navItems,
  isOpen,
  spots,
  onSelect,
}) {
  return (
    <AnimatePresence>
      {isOpen
        ? navItems.map((item, index) => {
          const Icon = item.icon;
          const spot = spots[index] || { dx: 0, dy: 0 };
          const cap = captionShift(spot);
          return (
            <motion.button
              key={item.name}
              type="button"
              className={`circ-nav-spoke ${item.active ? 'is-active' : ''}`}
              aria-label={item.name}
              disabled={item.disabled}
              initial={{ opacity: 0, x: 0, y: 0, scale: 0.4 }}
              animate={{ opacity: 1, x: spot.dx, y: spot.dy, scale: 1 }}
              exit={{ opacity: 0, x: 0, y: 0, scale: 0.4 }}
              transition={{ duration: 0.24, delay: index * 0.025, ease: [0.22, 1, 0.36, 1] }}
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                if (item.disabled) return;
                onSelect(item);
              }}
            >
              <span className="circ-nav-bubble">
                {Icon ? <Icon className="circ-nav-glyph" /> : null}
              </span>
              <span className="circ-nav-caption" style={{ '--cap-x': `${cap.x}px`, '--cap-y': `${cap.y}px` }}>{item.name}</span>
            </motion.button>
          );
        })
        : null}
    </AnimatePresence>
  );
}
