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
import re
import subprocess
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import tempfile

# Import m3u import functions
util_path = os.path.join(os.path.dirname(__file__), 'util')
if util_path not in sys.path:
    sys.path.append(util_path)
try:
    from m3u_import import parse_m3u, extract_audio_metadata, get_audio_duration_ffprobe, format_length as format_length_m3u, parse_length_seconds
    M3U_IMPORT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: M3U import not available: {e}")
    M3U_IMPORT_AVAILABLE = False

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
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if table exists first
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trackupdate'
        ''')
        
        if not cursor.fetchone():
            conn.close()
            return jsonify([])
        
        cursor.execute('''
            SELECT DISTINCT episodeNumber 
            FROM trackupdate 
            ORDER BY episodeNumber DESC
        ''')
        
        episodes = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(episodes)
    except Exception as e:
        print(f"Error getting episodes: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/episodes/<int:episode_number>', methods=['DELETE'])
def delete_episode(episode_number):
    """Delete all tracks for an episode"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM trackupdate WHERE episodeNumber = ?', (episode_number,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting episode: {e}")
        return jsonify({'error': str(e)}), 500

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

@app.route('/api/import/m3u', methods=['POST'])
def import_m3u():
    """Import tracks from an m3u file into the database"""
    if not M3U_IMPORT_AVAILABLE:
        return jsonify({'error': 'M3U import functionality not available'}), 500
    
    try:
        # Get form data
        if 'file' not in request.files:
            return jsonify({'error': 'No m3u file provided'}), 400
        
        m3u_file = request.files['file']
        if m3u_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        episode_number = request.form.get('episodeNumber')
        start_datetime_str = request.form.get('startDatetime')
        
        if not episode_number:
            return jsonify({'error': 'Episode number required'}), 400
        if not start_datetime_str:
            return jsonify({'error': 'Start datetime required'}), 400
        
        episode_number = int(episode_number)
        
        # Parse datetime
        try:
            start_datetime = parse_datetime(start_datetime_str)
        except ValueError as e:
            return jsonify({'error': f'Invalid datetime format: {str(e)}'}), 400
        
        # Save uploaded m3u file temporarily
        m3u_filename = secure_filename(m3u_file.filename)
        m3u_path = os.path.join(app.config['UPLOAD_FOLDER'], m3u_filename)
        m3u_file.save(m3u_path)
        
        # Parse m3u file
        tracks = parse_m3u(m3u_path)
        if not tracks:
            return jsonify({'error': 'No tracks found in m3u file'}), 400
        
        # Get database path and config
        db_path = get_db_path()
        config_path = os.path.expanduser('~/.trackupdaterc')
        cover_image_base_url = None
        
        if os.path.isfile(config_path):
            config = configparser.ConfigParser()
            config.read(config_path)
            try:
                cover_image_base_url = config.get('trackupdate', 'coverImageBaseURL')
            except (configparser.NoSectionError, configparser.NoOptionError):
                pass
        
        # Extract metadata from audio files
        m3u_base_dir = os.path.dirname(os.path.abspath(m3u_path))
        metadata_extracted = 0
        duration_updates = 0
        
        for track in tracks:
            original_duration = track.get('duration_seconds')
            if track.get('file_path'):
                file_path = track['file_path']
                if not os.path.isabs(file_path):
                    file_path = os.path.join(m3u_base_dir, file_path)
                file_path = os.path.normpath(os.path.abspath(file_path))
                
                # Get accurate duration
                if os.path.isfile(file_path):
                    accurate_duration = get_audio_duration_ffprobe(file_path)
                    if accurate_duration is not None:
                        track['duration_seconds'] = accurate_duration
                        track['length'] = format_length_m3u(accurate_duration)
                        if original_duration != track['duration_seconds']:
                            duration_updates += 1
                
                # Extract metadata
                metadata = extract_audio_metadata(track['file_path'], m3u_base_dir)
                if metadata:
                    if metadata.get('title'):
                        track['title'] = metadata['title'][:128]
                    if metadata.get('artist'):
                        track['artist'] = metadata['artist'][:128]
                    if metadata.get('album'):
                        track['album'] = metadata['album'][:128]
                    metadata_extracted += 1
            
            # Set artwork URL
            if cover_image_base_url:
                artwork_filename = start_datetime.strftime("%Y%m%d.jpg")
                track['artworkUrl'] = f"{cover_image_base_url}/{artwork_filename}"
            else:
                track['artworkUrl'] = ""
        
        # Connect to database and import tracks
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trackupdate (
            episodeNumber integer NOT NULL,
            uniqueId char(128),
            title char(128),
            artist char(128),
            album char(128),
            length char(128),
            startTime timestamp(128),
            "ignore" integer(128) NOT NULL DEFAULT(0),
            artworkUrl text(128)
            );''')
        
        # Calculate start times and insert tracks
        CONCAT_PADDING = 0.0
        current_time = start_datetime
        inserted_count = 0
        
        for i, track in enumerate(tracks, 1):
            track_start_time = current_time
            if i > 1:
                track_start_time += timedelta(seconds=CONCAT_PADDING)
            
            debool = 1 if track.get('ignore', False) else 0
            cursor.execute("INSERT INTO trackupdate VALUES (?,?,?,?,?,?,?,?,?)",
                         (episode_number,
                          track.get('uniqueId', ''),
                          track.get('title', ''),
                          track.get('artist', ''),
                          track.get('album', ''),
                          track.get('length', '0:00'),
                          format_timestamp(track_start_time),
                          debool,
                          track.get('artworkUrl', '')))
            
            current_time += timedelta(seconds=track.get('duration_seconds', 0))
            inserted_count += 1
        
        conn.commit()
        conn.close()
        
        # Clean up temporary m3u file
        try:
            os.unlink(m3u_path)
        except OSError:
            pass
        
        return jsonify({
            'success': True,
            'tracksImported': inserted_count,
            'metadataExtracted': metadata_extracted,
            'durationUpdates': duration_updates,
            'episodeNumber': episode_number
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def parse_datetime(datetime_str):
    """Parse datetime string in various formats"""
    formats = [
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S.%f',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse datetime: {datetime_str}")

@app.route('/api/episodes/<int:episode_number>/import', methods=['POST'])
def import_episode(episode_number):
    """Import tracks from JSON data into the database"""
    try:
        data = request.json
        
        if not data or 'tracks' not in data:
            return jsonify({'error': 'Invalid JSON format. Expected object with "tracks" array.'}), 400
        
        tracks_data = data['tracks']
        first_time_str = data.get('firstTime')
        
        # Parse first time if provided
        if first_time_str:
            try:
                first_time = datetime.fromisoformat(first_time_str.replace('Z', '+00:00'))
            except:
                first_time = None
        else:
            first_time = None
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete existing tracks for this episode
        cursor.execute('DELETE FROM trackupdate WHERE episodeNumber = ?', (episode_number,))
        
        # Insert new tracks
        inserted_count = 0
        for track_data in tracks_data:
            # Calculate start time
            if first_time and 'startTimeSeconds' in track_data:
                start_time = first_time + timedelta(seconds=track_data['startTimeSeconds'])
            else:
                # Fallback to current time if no first time provided
                start_time = datetime.now() + timedelta(seconds=track_data.get('startTimeSeconds', 0))
            
            cursor.execute("INSERT INTO trackupdate VALUES (?,?,?,?,?,?,?,?,?)",
                         (episode_number,
                          track_data.get('uniqueId', ''),
                          track_data.get('title', ''),
                          track_data.get('artist', ''),
                          track_data.get('album', ''),
                          track_data.get('length', '0:00'),
                          format_timestamp(start_time),
                          1 if track_data.get('ignore', False) else 0,
                          track_data.get('artworkUrl', '')))
            inserted_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'tracksImported': inserted_count,
            'episodeNumber': episode_number
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print(f"Starting track editor web server...")
    print(f"Database path: {get_db_path()}")
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)

