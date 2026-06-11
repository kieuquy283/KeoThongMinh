## KeoBot 2D mascot assets

This folder contains the public 2D mascot PNG assets used by the frontend.

Canonical asset files:

- `keobot_idle.png`
- `keobot_listening.png`
- `keobot_thinking.png`
- `keobot_speaking_1.png`
- `keobot_speaking_2.png`
- `keobot_speaking_3.png`
- `keobot_happy.png`
- `keobot_error.png`
- `keobot_reminder.png`
- `keobot_blink_1.png`
- `keobot_blink_2.png`
- `keobot_wave.png`
- `keobot_celebrate.png`
- `keobot_thinking_alt.png`
- `keobot_loading.png`
- `keobot_goodbye.png`
- `keobot_confused.png`
- `keobot_sad.png`
- `keobot_sleepy.png`
- `keobot_surprised_alt.png`
- `keobot_processing.png`
- `keobot_calm.png`

Usage summary:

- Base states: idle, listening, thinking, speaking, error, reminder, loading
- Emotion overrides: happy, celebrate, confused, sleepy, calm, surprised, sad
- Speaking uses the `keobot_speaking_1..3.png` frame loop
- Blink uses `keobot_blink_1.png` and `keobot_blink_2.png` during calm idle states

Notes:

- `keobot_mascot.png` is a legacy single-image asset kept for backward compatibility during migration.
- This phase uses a 2D image-based mascot system only. It does not use Live2D, VRM, GLB, or 3D avatar rendering.
