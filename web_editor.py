#!/usr/bin/env python3

"""
Web-based track editor for trackupdate database.
Allows visual editing of track times with waveform display.
"""

import os
import sys
import sqlite3
import configparser
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Get database path from config
def get_db_path():
    config_path = os.path.expanduser('~/.trackupdaterc')
    if not os.path.isfile(config_path):
        # Fallback to default
        return os.path.expanduser('~/src/trackupdate/db/trackupdate.sqlite')
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    try:
        db_path = config.get('SqliteTarget', 'dbPath')
        return os.path.expanduser(db_path)
    except (configparser.NoSectionError, configparser.NoOptionError):
        # Fallback to default
        return os.path.expanduser('~/src/trackupdate/db/trackupdate.sqlite')

def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def parse_length(length_str):
    """Parse length string like '4:20' into seconds"""
    if not length_str:
        return 0
    parts = length_str.split(':')
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0

def format_length(seconds):
    """Format seconds into 'M:SS' or 'H:MM:SS' format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"

def format_timestamp(dt):
    """Format datetime to match database format (space-separated, not ISO T-separated)"""
    # Use strftime to ensure space separator instead of T
    return dt.strftime('%Y-%m-%d %H:%M:%S.%f')

@app.route('/')
def index():
    return render_template('editor.html')

@app.route('/api/episodes')
def get_episodes():
    """Get list of all episode numbers"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT episodeNumber 
        FROM trackupdate 
        ORDER BY episodeNumber DESC
    ''')
    
    episodes = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(episodes)

@app.route('/api/episodes/<int:episode_number>/tracks')
def get_tracks(episode_number):
    """Get all tracks for an episode"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT rowid, * FROM trackupdate
        WHERE episodeNumber = ?
        ORDER BY datetime(startTime) ASC
    ''', (episode_number,))
    
    tracks = []
    first_time = None
    
    for row in cursor.fetchall():
        start_time = datetime.fromisoformat(row['startTime'])
        if first_time is None:
            first_time = start_time
        
        elapsed = (start_time - first_time).total_seconds()
        length_seconds = parse_length(row['length'])
        
        # Use rowid as ID if uniqueId is not available
        track_id = row['uniqueId'] if row['uniqueId'] else f"rowid_{row['rowid']}"
        
        track = {
            'id': track_id,
            'rowid': row['rowid'],
            'episodeNumber': row['episodeNumber'],
            'uniqueId': row['uniqueId'],
            'title': row['title'] or '',
            'artist': row['artist'] or '',
            'album': row['album'] or '',
            'length': row['length'] or '0:00',
            'lengthSeconds': length_seconds,
            'startTime': row['startTime'],
            'startTimeSeconds': elapsed,
            'ignore': bool(row['ignore']),
            'artworkUrl': row['artworkUrl'] or ''
        }
        tracks.append(track)
    
    conn.close()
    
    return jsonify({
        'tracks': tracks,
        'firstTime': format_timestamp(first_time) if first_time else None
    })

@app.route('/api/episodes/<int:episode_number>/tracks', methods=['POST'])
def create_track(episode_number):
    """Create a new track"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the first track time to calculate relative position
    cursor.execute('''
        SELECT startTime FROM trackupdate
        WHERE episodeNumber = ?
        ORDER BY startTime LIMIT 1
    ''', (episode_number,))
    
    first_row = cursor.fetchone()
    if first_row:
        first_time = datetime.fromisoformat(first_row['startTime'])
        start_time = first_time + timedelta(seconds=data['startTimeSeconds'])
    else:
        # No existing tracks, use current time as base and add the offset
        start_time = datetime.now() + timedelta(seconds=data.get('startTimeSeconds', 0))
    
    cursor.execute('''
        INSERT INTO trackupdate 
        (episodeNumber, uniqueId, title, artist, album, length, startTime, "ignore", artworkUrl)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        episode_number,
        data.get('uniqueId'),
        data.get('title', ''),
        data.get('artist', ''),
        data.get('album', ''),
        data.get('length', '0:00'),
        format_timestamp(start_time),
        1 if data.get('ignore', False) else 0,
        data.get('artworkUrl', '')
    ))
    
    conn.commit()
    track_id = cursor.lastrowid
    conn.close()
    
    return jsonify({'success': True, 'id': track_id}), 201

@app.route('/api/episodes/<int:episode_number>/tracks/<track_id>', methods=['PUT'])
def update_track(episode_number, track_id):
    """Update a track"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get first track time for relative positioning
    cursor.execute('''
        SELECT startTime FROM trackupdate
        WHERE episodeNumber = ?
        ORDER BY startTime LIMIT 1
    ''', (episode_number,))
    
    first_row = cursor.fetchone()
    if first_row:
        first_time = datetime.fromisoformat(first_row['startTime'])
        start_time = first_time + timedelta(seconds=data['startTimeSeconds'])
    else:
        start_time = datetime.now()
    
    # Find track by uniqueId or rowid
    if track_id.startswith('rowid_'):
        # Update by rowid
        rowid = int(track_id.split('_')[1])
        cursor.execute('''
            UPDATE trackupdate
            SET uniqueId = ?, title = ?, artist = ?, album = ?, 
                length = ?, startTime = ?, "ignore" = ?, artworkUrl = ?
            WHERE rowid = ?
        ''', (
            data.get('uniqueId'),
            data.get('title', ''),
            data.get('artist', ''),
            data.get('album', ''),
            data.get('length', '0:00'),
            format_timestamp(start_time),
            1 if data.get('ignore', False) else 0,
            data.get('artworkUrl', ''),
            rowid
        ))
    else:
        # Update by uniqueId
        cursor.execute('''
            UPDATE trackupdate
            SET uniqueId = ?, title = ?, artist = ?, album = ?, 
                length = ?, startTime = ?, "ignore" = ?, artworkUrl = ?
            WHERE episodeNumber = ? AND uniqueId = ?
        ''', (
            data.get('uniqueId'),
            data.get('title', ''),
            data.get('artist', ''),
            data.get('album', ''),
            data.get('length', '0:00'),
            format_timestamp(start_time),
            1 if data.get('ignore', False) else 0,
            data.get('artworkUrl', ''),
            episode_number,
            track_id
        ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/episodes/<int:episode_number>/tracks/<track_id>', methods=['DELETE'])
def delete_track(episode_number, track_id):
    """Delete a track"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if track_id.startswith('rowid_'):
        # Delete by rowid
        rowid = int(track_id.split('_')[1])
        cursor.execute('DELETE FROM trackupdate WHERE rowid = ?', (rowid,))
    else:
        # Delete by uniqueId
        cursor.execute('''
            DELETE FROM trackupdate
            WHERE episodeNumber = ? AND uniqueId = ?
        ''', (episode_number, track_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/episodes/<int:episode_number>/tracks/shift', methods=['POST'])
def shift_tracks(episode_number):
    """Shift a range of tracks by a time delta"""
    data = request.json
    start_index = data.get('startIndex', 0)
    end_index = data.get('endIndex')
    delta_seconds = data.get('deltaSeconds', 0)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all tracks for the episode
    cursor.execute('''
        SELECT rowid, startTime FROM trackupdate
        WHERE episodeNumber = ?
        ORDER BY startTime
    ''', (episode_number,))
    
    tracks = cursor.fetchall()
    
    if end_index is None:
        end_index = len(tracks)
    
    # Update tracks in range
    for i in range(start_index, min(end_index, len(tracks))):
        track = tracks[i]
        old_time = datetime.fromisoformat(track['startTime'])
        new_time = old_time + timedelta(seconds=delta_seconds)
        
        cursor.execute('''
            UPDATE trackupdate
            SET startTime = ?
            WHERE rowid = ?
        ''', (format_timestamp(new_time), track['rowid']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle audio file upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    return jsonify({
        'success': True,
        'filename': filename,
        'url': f'/api/audio/{filename}'
    })

@app.route('/api/audio/<filename>')
def serve_audio(filename):
    """Serve uploaded audio files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    print(f"Starting track editor web server...")
    print(f"Database path: {get_db_path()}")
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)

