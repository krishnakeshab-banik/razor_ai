import { useApp } from '../AppContext';
import { formatPaise, titleCaseType } from '../lib/format';

export default function ExceptionDrawer() {
  const { drawerOpen, drawerData, closeDrawer, handleResolveException, resolvingId } = useApp();

  return (
    <>
      <div className={`drawer-overlay ${drawerOpen ? 'open' : ''}`} onClick={closeDrawer} />
      <div className={`drawer ${drawerOpen ? 'open' : ''}`}>
        <div className="drawer-header">
          <h3>Exception deep-dive</h3>
          <button className="drawer-close" onClick={closeDrawer} type="button">✕</button>
        </div>
        <div className="drawer-body">
          <div className="drawer-sec">
            <label>Payment ID</label>
            <div className="drawer-valHighlight">{drawerData.payment_id}</div>
          </div>
          <div className="drawer-grid">
            <div className="drawer-sec">
              <label>Mismatch</label>
              <div className="drawer-val">{titleCaseType(drawerData.mismatch_type)}</div>
            </div>
            <div className="drawer-sec">
              <label>Delta</label>
              <div className="drawer-val text-danger">
                {drawerData.delta !== null && drawerData.delta !== undefined ? formatPaise(drawerData.delta) : '—'}
              </div>
            </div>
          </div>
          <div className="drawer-sec">
            <label>Plain-language diagnosis</label>
            <div className="drawer-explanation">{drawerData.explanation}</div>
          </div>
          <div className="drawer-actions">
            <button
              className="btn btn-secondary-outline btn-block"
              type="button"
              disabled={resolvingId === drawerData.payment_id}
              onClick={() => {
                handleResolveException(drawerData.payment_id, 'escalate');
                closeDrawer();
              }}
            >
              Escalate — keep on the exception list
            </button>
            <button
              className="btn btn-primary btn-block"
              type="button"
              disabled={resolvingId === drawerData.payment_id}
              onClick={() => {
                handleResolveException(drawerData.payment_id, 'apply_fix');
                closeDrawer();
              }}
            >
              Apply suggested fix
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
