ARCADE CAROUSEL — Windows game launcher
========================================

What it does
- Full-screen horizontal game carousel.
- Scans the `Games` folder for Windows `.lnk` shortcuts.
- Shows matching cover art automatically when the filename matches.
- Refreshes the library automatically while running.
- Gamepad navigation and launch; keyboard fallback.
- Can be started with Windows using the included batch file.

QUICK START
1. Double-click `install_requirements.bat`.
   - Automatically installs Python 3.12 (if not already installed).
   - Automatically configures Windows System & User PATH.
   - Installs and upgrades pip and pygame.
   - Verifies Tkinter, Pygame, and administrator APIs.
2. Put game shortcuts (`.lnk`) in the `Games` folder.
3. Optional: place cover art in the same `Games` folder with the same base name.
   Example:
       Games\Tekken 7.lnk
       Games\Tekken 7.png
   Supported artwork: PNG, JPG, JPEG, WEBP.
4. Double-click `run_arcade.bat`.
5. To change insert-coin input or added time, double-click `run_coin_mapper.bat`.
   Click the input field and press a keyboard key or controller button, D-pad direction,
   stick, or trigger. Choose the minutes added and click Save time.

CONTROLS
- Insert Coin: The configured insert-coin key, controller button, or trigger adds the minutes set in Coin Mapper.
- Universal Gamepad Support: Full native XInput (Xbox 360, Xbox One, Xbox Series X/S, 8BitDo, Logitech X-mode), SDL2 GameController, and DirectInput / HID (DualShock 4, DualSense, Switch Pro, USB arcade fightsticks/encoders like Zero Delay and Brook).
- Hot-plugging: Gamepads can be plugged or unplugged at any time while the carousel is running.
- D-pad Left / Right or Left/Right Analog Stick: previous / next game.
- Left Bumper (LB) / Right Bumper (RB): quick jump 5 games backward / forward.
- Gamepad A / Cross or Start button: launch selected game.
- Gamepad B / Circle: exit launcher.
- Back / Select button: refresh library.
- Keyboard: Left / Right arrows or A / D, Enter / Space to launch, F5 refresh, Esc to exit.

AUTO-START WITH WINDOWS
1. Double-click `install_autostart.bat` to add a hidden startup entry.
   Alternatively, copy `run_arcade.vbs` into the Startup folder opened with `shell:startup`.
2. Keep the app folder in its current location; the launcher uses its own folder.

NOTES
- This is a Python desktop app. Running `install_requirements.bat` installs all necessary components.
- Direct Native XInput integration via `xinput1_4.dll` / `xinput1_3.dll` guarantees that Xbox/XInput controllers work unconditionally, including detecting coin insertion in the background while heavy games (Tekken 8, GTA V) are running.
- Analog Triggers (LT / RT) on 6-axis controllers are cleanly separated from sticks, preventing trigger pulls from scrolling the carousel.
- The launcher uses Windows' own shortcut handling (`os.startfile`) to open `.lnk` files.
- The remaining credit timer stays visible in a floating click-through overlay while a game is running.
- When the game timer ends while a game is running, player input is NOT blocked; instead, a full-screen, click-through 2-minute warning overlay appears. If a coin is inserted within those 2 minutes, normal play resumes; if no coin is added, the game is terminated and the system returns to the Arcade UI.
- Coin Mapper settings are saved in `coin_mapper_config.json` and load automatically in the launcher.
- To exit the full-screen launcher, press B or Esc.
- If a shortcut's target requires administrator privileges or a special launcher, Windows may show its usual prompt.
