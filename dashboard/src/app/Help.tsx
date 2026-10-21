// The Help dialog: what each page is for, what each button does, and the keys that work. Also
// restarts the guided tour.
import { useAppStore } from "./appStore";
import { PAGE_INFO, NAV_ITEMS } from "./route";
import { useUi } from "./ui";
import { Modal } from "../pages/ui";

export const SHORTCUTS: [string, string][] = [
  ["?", "Open or close this Help"],
  ["Esc", "Close a dialog or a pop-up"],
  ["Space", "On a shipment: play or pause"],
  ["R", "On a shipment: restart the journey"],
  ["1 to 5", "On the Shipments page: open that shipment"],
  ["G", "Go to the Story"],
  ["H", "Go to Home"],
  ["M", "Turn reduced motion on or off"],
  ["F", "Full screen"],
  ["Q", "Change the 3D picture quality (Technical)"],
  ["D", "Show or hide the performance numbers (Technical)"],
];

const BUTTONS: [string, string][] = [
  ["Play, Pause, Restart", "Control the replay of a shipment's journey."],
  ["Slow, Normal, Fast", "How quickly the journey replays."],
  ["Approve", "Accept the recommendation (demo: this changes this screen only)."],
  ["Choose a different action", "Pick another action and give a reason of at least 10 characters."],
  ["Reject", "Turn the recommendation down. A reason is required."],
  ["Check the records", "Show the recorded result of checking every signed record."],
  ["Try to change a record", "Show the recorded result of a real change made to a copy."],
  ["Simple / Technical", "Switch between plain words and the engineers' words."],
  ["Light / Dark / System", "Choose the colour theme."],
];

export function Help() {
  const open = useAppStore((s) => s.helpOpen);
  const setOpen = useAppStore((s) => s.setHelpOpen);
  const startTour = useUi((s) => s.startTour);
  if (!open) return null;
  return (
    <Modal title="Help" onClose={() => setOpen(false)} wide>
      <p>PotencyGuard shows sample medicine shipments from a simulation. Nothing here is real, and nothing you do is sent anywhere.</p>
      <h3>The pages</h3>
      <dl className="help-list">
        {NAV_ITEMS.map((n) => (
          <div key={n.page}><dt>{n.label}</dt><dd>{PAGE_INFO[n.page].lead}</dd></div>
        ))}
      </dl>
      <h3>The buttons</h3>
      <dl className="help-list">
        {BUTTONS.map(([k, v]) => (
          <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
        ))}
      </dl>
      <h3>Keyboard shortcuts</h3>
      <dl className="help-list">
        {SHORTCUTS.map(([k, v]) => (
          <div key={k}><dt><kbd>{k}</kbd></dt><dd>{v}</dd></div>
        ))}
      </dl>
      <div className="modal-actions">
        <button type="button" className="btn primary" onClick={() => { setOpen(false); startTour(); }}>Start the guided tour</button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>Close</button>
      </div>
    </Modal>
  );
}
