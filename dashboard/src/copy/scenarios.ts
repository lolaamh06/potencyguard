// Plain-language titles and one-sentence descriptions of the five sample shipments. These are
// descriptions of what each sample demonstrates (words only; every figure comes from the data).
import type { ScenarioId } from "../controlroom/logic";

export interface ScenarioCopy {
  title: string;
  blurb: string;
}

export const SCENARIO_COPY: Record<ScenarioId, ScenarioCopy> = {
  baseline_ok: { title: "A normal journey", blurb: "Nothing goes wrong. It shows what a healthy shipment looks like." },
  door_open_excursion: { title: "A door left open", blurb: "The box warms up for a while when its door is left open, then recovers." },
  reefer_failure: { title: "The cooling fails", blurb: "The cooling stops working and does not come back. The system recommends a different plan." },
  spoof_attempt: { title: "Readings that look false", blurb: "The temperature readings do something a real box cannot do, so the data is not trusted." },
  hidden_spoilage: { title: "A cover-up", blurb: "The readings are made to look fine while the medicine is really being harmed. The checks notice." },
};

export const START_HERE: ScenarioId = "reefer_failure";
