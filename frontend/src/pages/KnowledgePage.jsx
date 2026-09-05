import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { useApp } from '../AppContext';
import { formatTimestamp, titleCaseType } from '../lib/format';
import { useLanguage } from '../i18n/LanguageContext';

const MISMATCH_OPTIONS = [
  { value: 'fee_miscalculation', label: 'Fee miscalculation' },
  { value: 'tax_line_mismatch', label: 'GST line mismatch' },
  { value: 'unaccounted_refund', label: 'Unaccounted refund' },
  { value: 'timing_mismatch', label: 'Timing mismatch' },
  { value: 'unknown_adjustment', label: 'Unknown adjustment' },
];

export default function KnowledgePage() {
  const { triggerToast, reconciliationRun } = useApp();
  const { t } = useLanguage();
  const [rules, setRules] = useState([]);
  const [form, setForm] = useState({
    title: '',
    guidance: '',
    mismatch_type: 'fee_miscalculation',
    payment_method: '',
    merchant_key: '',
    resolution_category: 'legitimate_adjustment',
  });

  const load = async () => {
    try {
      const data = await api.rules();
      setRules(data.rules || []);
    } catch {
      setRules([]);
    }
  };

  useEffect(() => { load(); }, []);

  const create = async (event) => {
    event.preventDefault();
    try {
      await api.createRule(form);
      triggerToast('Rule saved. It only guides investigation text — it does not auto-fix the books.', 'success');
      setForm({ ...form, title: '', guidance: '' });
      load();
    } catch (error) {
      triggerToast(error.message || 'Could not save the rule.', 'danger');
    }
  };

  return (
    <div className="db-page">
      <div className="db-page-heading" data-tour="rules-purpose">
        <div>
          <p className="bank-kicker">Investigation knowledge</p>
          <h2 className="db-page-title">{t('pages.rulesTitle')}</h2>
          <p className="db-page-sub">Write standing guidance the controller can quote when investigating an exception. Rules never post a settlement, never invent a UTR, and never auto-resolve money.</p>
        </div>
      </div>

      <div className="rules-intro">
        <div>
          <span>1</span>
          <strong>What this is</strong>
          <p>A notebook of human policy — for example “UPI fee rounding of ₹1 is expected on this MID”.</p>
        </div>
        <div>
          <span>2</span>
          <strong>What it changes</strong>
          <p>Investigation and chat can mention the rule. The match engine still uses arithmetic, not these notes.</p>
        </div>
        <div>
          <span>3</span>
          <strong>What it will not do</strong>
          <p>It will not close exceptions, move cash, or pretend a missing bank credit arrived.</p>
        </div>
      </div>

      <div className="bank-split">
        <form className="db-card" data-tour="rules-form" onSubmit={create}>
          <h3 className="db-card-title">Add a standing rule</h3>
          <p className="db-card-sub">Keep it specific. Name the mismatch type it applies to.</p>
          <label className="bank-field">Title
            <input className="db-exc-search" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="e.g. UPI rounding under ₹1 is acceptable" required />
          </label>
          <label className="bank-field">Guidance for investigators
            <textarea className="db-exc-search" rows={4} value={form.guidance} onChange={(event) => setForm({ ...form, guidance: event.target.value })} placeholder="What should a human check, and when is a waive allowed?" required />
          </label>
          <label className="bank-field">Applies to mismatch
            <select className="db-filter-select" value={form.mismatch_type} onChange={(event) => setForm({ ...form, mismatch_type: event.target.value })}>
              {MISMATCH_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <div className="db-exc-filters">
            <input className="db-exc-search" placeholder="Payment method (optional)" value={form.payment_method} onChange={(event) => setForm({ ...form, payment_method: event.target.value })} />
            <input className="db-exc-search" placeholder="Merchant / customer key (optional)" value={form.merchant_key} onChange={(event) => setForm({ ...form, merchant_key: event.target.value })} />
          </div>
          <button className="db-topbar-cta sticky-page-cta" type="submit">Save rule</button>
        </form>

        <div className="db-card" data-tour="rules-list">
          <div className="bank-table-head">
            <h3 className="db-card-title">Saved rules</h3>
            <span>{rules.length} stored</span>
          </div>
          {!reconciliationRun && <p className="db-card-sub">Rules still apply after the next reconcile. They only influence investigation text.</p>}
          {rules.length ? rules.map((rule) => (
            <article className={`rules-card ${rule.enabled ? '' : 'is-off'}`} key={rule.id}>
              <header>
                <strong>{rule.title}</strong>
                <span className={`ops-workflow-pill ${rule.enabled ? 'resolved' : 'open'}`}>{rule.enabled ? 'Active' : 'Disabled'}</span>
              </header>
              <p>{rule.guidance}</p>
              <dl>
                <div><dt>Mismatch</dt><dd>{titleCaseType(rule.mismatch_type)}</dd></div>
                <div><dt>Origin</dt><dd>{rule.origin || 'human'}</dd></div>
                <div><dt>Created</dt><dd>{formatTimestamp(rule.created_at)}</dd></div>
                <div><dt>Quoted</dt><dd>{rule.influence_count || 0}×</dd></div>
              </dl>
              <div className="db-whatif-actions">
                <button className="db-filter-btn" type="button" onClick={async () => { await api.updateRule(rule.id, { enabled: !rule.enabled }); load(); }}>
                  {rule.enabled ? 'Disable' : 'Enable'}
                </button>
                <button className="db-ghost-btn" type="button" onClick={async () => { await api.deleteRule(rule.id); load(); }}>Delete</button>
              </div>
            </article>
          )) : (
            <p className="db-table-empty">No human rules yet. Add one on the left — it will not auto-fix anything.</p>
          )}
        </div>
      </div>
    </div>
  );
}
