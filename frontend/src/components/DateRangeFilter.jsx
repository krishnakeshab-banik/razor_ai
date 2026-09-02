import React from 'react';

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

export default function DateRangeFilter({ value = EMPTY_DATE_FILTER, onChange, showTime = true, dataTour }) {
  const update = (patch) => onChange({ ...value, ...patch });

  return (
    <div className="db-date-filter" data-tour={dataTour}>
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
    </div>
  );
}
