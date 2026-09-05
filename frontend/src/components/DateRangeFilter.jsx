import React, { useState } from 'react';

const PRESETS = [
  { id: 'all', label: 'All time' },
  { id: 'today', label: 'Today' },
  { id: 'yesterday', label: 'Yesterday' },
  { id: 'last_7_days', label: 'Last 7 days' },
  { id: 'last_30_days', label: 'Last 30 days' },
  { id: 'custom', label: 'Custom' },
];

export const EMPTY_DATE_FILTER = {
  preset: 'all',
  start: '',
  end: '',
  startTime: '00:00',
  endTime: '23:59',
};

export function dateQuery(filter = EMPTY_DATE_FILTER) {
  const params = new URLSearchParams();
  params.set('preset', filter.preset || 'all');
  if (filter.preset === 'custom') {
    if (filter.start) params.set('start', filter.start);
    if (filter.end) params.set('end', filter.end);
    if (filter.startTime) params.set('start_time', filter.startTime);
    if (filter.endTime) params.set('end_time', filter.endTime);
  }
  return params.toString();
}

function DateControls({ value, update, showTime }) {
  return (
    <>
      <div className="db-date-presets">
        {PRESETS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`db-date-chip ${value.preset === item.id ? 'active' : ''}`}
            onClick={() => update({ preset: item.id })}
          >
            {item.label}
          </button>
        ))}
      </div>
      {value.preset === 'custom' && (
        <div className="db-date-custom">
          <label>
            Start date
            <input type="date" value={value.start} onChange={(event) => update({ start: event.target.value })} />
          </label>
          {showTime && (
            <label>
              Start time
              <input type="time" value={value.startTime} onChange={(event) => update({ startTime: event.target.value })} />
            </label>
          )}
          <label>
            End date
            <input type="date" value={value.end} onChange={(event) => update({ end: event.target.value })} />
          </label>
          {showTime && (
            <label>
              End time
              <input type="time" value={value.endTime} onChange={(event) => update({ endTime: event.target.value })} />
            </label>
          )}
        </div>
      )}
    </>
  );
}

export function MobileFilterPack({ children, label = 'Filters' }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mobile-filter-pack">
      <button type="button" className="mobile-filter-trigger" onClick={() => setOpen(true)}>
        <span>{label}</span>
        <span aria-hidden="true">▾</span>
      </button>
      <div className={`mobile-filter-body${open ? ' is-sheet' : ''}`}>
        {open ? (
          <button type="button" className="db-date-sheet-scrim" aria-label="Close filters" onClick={() => setOpen(false)} />
        ) : null}
        <div className="mobile-filter-panel">
          <div className="db-date-sheet-head">
            <h3>{label}</h3>
            <button type="button" className="exc-sheet-close" onClick={() => setOpen(false)} aria-label="Close filters">✕</button>
          </div>
          {children}
          <button type="button" className="db-topbar-cta mobile-filter-done" onClick={() => setOpen(false)}>Done</button>
        </div>
      </div>
    </div>
  );
}

export default function DateRangeFilter({ value = EMPTY_DATE_FILTER, onChange, showTime = true, dataTour, mobileSheet = true }) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const update = (patch) => onChange({ ...value, ...patch });
  const presetLabel = PRESETS.find((item) => item.id === value.preset)?.label || 'All time';

  return (
    <div className={`db-date-filter${mobileSheet ? ' db-date-filter-sheetable' : ''}`} data-tour={dataTour}>
      {mobileSheet && (
        <>
          <button type="button" className="db-date-sheet-trigger" onClick={() => setSheetOpen(true)}>
            <span>{presetLabel}</span>
            <span aria-hidden="true">▾</span>
          </button>
          <div className={`db-date-sheet-layer${sheetOpen ? ' is-open' : ''}`}>
            <button type="button" className="db-date-sheet-scrim" aria-label="Close date filter" onClick={() => setSheetOpen(false)} />
            <div className="db-date-sheet" role="dialog" aria-label="Date range">
              <div className="db-date-sheet-head">
                <h3>Date range</h3>
                <button type="button" className="exc-sheet-close" onClick={() => setSheetOpen(false)} aria-label="Close date filter">✕</button>
              </div>
              <DateControls value={value} update={update} showTime={showTime} />
              <button type="button" className="db-topbar-cta" onClick={() => setSheetOpen(false)}>Apply</button>
            </div>
          </div>
        </>
      )}
      <div className={mobileSheet ? 'db-date-filter-inline' : ''}>
        <DateControls value={value} update={update} showTime={showTime} />
      </div>
    </div>
  );
}
