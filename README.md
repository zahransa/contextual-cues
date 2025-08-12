# Contextual Cueing (T among Ls) with Vibration

Pygame implementation of the classic **contextual cueing** visual search task.  
Participants search for a rotated **T** among many **L** distractors. Some spatial layouts repeat across blocks (“**old**”); others are novel (“**new**”). With practice, reactions become faster in old layouts—even without explicit awareness.

![Example stimulus](assets/stimulus.png)

## What’s special in this version
- **Harder displays**: every **L** gets a new **orientation** (ul/ur/dl/dr) **and color** each trial.
- **T target color** also randomizes each trial (color is non-diagnostic).
- **Vibration timing**: on a subset of trials, a vibration (via Arduino) is sent just **before the estimated response**, using a per-subject **staircase** threshold.
- **Block feedback**: mean RT and accuracy after each block.

## Files
- `fullcodecolors.py` – main experiment.
- `contextual_trials_chun1998_black_FULL.csv` – trial layouts (positions + condition labels).
- Outputs (per subject):
  - `results_chun1998_black_{subject}.csv`
  - `vibration_responses_{subject}.csv`
  - `staircase_results_{subject}.csv`
  - `summary_rt_plot_{subject}.png`

## Requirements
Python 3.9+  
```bash
pip install pygame pandas matplotlib pyserial
