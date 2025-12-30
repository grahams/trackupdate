# Track Editor Web Interface

A web-based tool for visually editing track times in the trackupdate database. Features waveform visualization with draggable track markers, making it easy to adjust, add, remove, and shift track records.

## Features

- **Waveform Visualization**: Upload an audio file and see a visual waveform
- **Track Markers**: Tracks from the database are displayed as markers on the waveform
- **Drag to Adjust**: Drag markers on the waveform to adjust track start times
- **Add/Edit/Delete Tracks**: Full CRUD operations for track records
- **Bulk Shift**: Shift a range of tracks by a time delta
- **Real-time Playback**: Play audio and see current position on waveform

## Installation

1. Install Flask (if not already installed):
   ```bash
   pip install flask
   ```
   
   Or add to your conda environment:
   ```bash
   conda install -c conda-forge flask
   ```

2. Ensure your `~/.trackupdaterc` config file has the `[SqliteTarget]` section with the `dbPath` setting, or the editor will use the default path.

## Usage

1. Start the web server:
   ```bash
   python web_editor.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

3. **Select an Episode**: Choose an episode number from the dropdown, or create a new one

4. **Upload Audio**: Drag and drop an audio file (or click to browse) to load it into the waveform viewer

5. **Edit Tracks**:
   - Click "Add Track" to create a new track at the current playback position
   - Click "Edit" on any track to modify its details
   - Drag markers on the waveform to adjust track start times
   - Click "Delete" to remove a track
   - Use "Shift Selected" to shift a range of tracks by a time delta

## API Endpoints

The web editor provides the following REST API endpoints:

- `GET /api/episodes` - List all episode numbers
- `GET /api/episodes/<episode>/tracks` - Get all tracks for an episode
- `POST /api/episodes/<episode>/tracks` - Create a new track
- `PUT /api/episodes/<episode>/tracks/<track_id>` - Update a track
- `DELETE /api/episodes/<episode>/tracks/<track_id>` - Delete a track
- `POST /api/episodes/<episode>/tracks/shift` - Shift a range of tracks
- `POST /api/upload` - Upload an audio file
- `GET /api/audio/<filename>` - Serve uploaded audio files

## Notes

- Uploaded audio files are stored in a temporary directory and will be deleted when the server stops
- The waveform uses WaveSurfer.js for visualization
- Track markers are color-coded: blue for normal tracks, red for ignored tracks
- All changes are saved directly to the database

