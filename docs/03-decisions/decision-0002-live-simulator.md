# Decision 0002: The live simulator

Date: 2026-10-20

Phase 1 built a simulator that computed a whole trip, wrote a file and replayed it. For stage demos we need a simulator that feels alive. These are the decisions that make that possible, and why.

**1. The cooling unit cycles on and off.** The old model held the box at exactly the setpoint, a flat line that no real cooled box produces. Now the unit switches on a little above the setpoint and off a little below it, so the temperature wobbles around the setpoint. A flat line also made later detectors too easy, and made a "frozen sensor" attack look like normal behaviour. The unit never heats, which is what lets a freezing night really freeze the box.

**2. One physics path.** The box advances one sample at a time in a single engine. The old batch function is now a loop over that engine. If two code paths existed they would slowly disagree, and a bug fixed in one would stay in the other.

**3. Three separate random streams from one seed.** Sensor noise, scenario parameters and free-run faults each have their own stream. Noise uses exactly three random numbers per sample no matter what is happening, so injecting a fault never changes the noise that follows. The same seed always gives the same file, which tests and recorded demo videos depend on. A random run still prints its seed, so it can be repeated.

**4. Random ranges plus guaranteed behaviour.** Any number in a scenario can be a range, drawn once per run, so every live run looks different. Each scenario also carries an `expect` block, for example "the box ends up above the upper limit". The tests run 200 seeds per scenario and fail if any seed breaks a guarantee. So variety can never turn a "reefer failure" into a trip that does not fail.

**5. Faults you can inject while it runs.** A person can break the cooling, open the door, falsify the sensor and so on, and the next readings respond. The list of faults is fixed and every fault is checked before it is applied; a bad one is refused with a message and the run carries on untouched. Each injected fault is recorded in the history with its origin, so a detector can later be scored against what really happened.

**6. Free-run trips.** A trip can be invented from a seed with no scenario file. Faults are planned an hour at a time from placeholder probabilities. Some trips have no fault. A sensor lie can only begin after a real cooling or heat problem, because a lie with nothing to hide is not a useful test.

**7. Recordings carry more truth.** Recordings are now schema 0.2 and the ground-truth file lists the compressor state, the cooling factor, the resolved random numbers and every event with its origin. The old schema 0.1 is refused with a clear message.

Every number involved is still a placeholder, marked "not sourced [SOURCE NEEDED]".
