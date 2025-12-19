#!/usr/bin/env python3

# Copyright (c) 2024 Sean M. Graham <www.sean-graham.com>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import os
import sys
import sqlite3
import argparse
import configparser
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

try:
    from mutagen import File
    from mutagen.id3 import ID3NoHeaderError
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

def parse_length_seconds(length_str):
    """Parse length string in MM:SS format and return total seconds"""
    parts = length_str.split(':')
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    else:
        return 0

def format_length(seconds):
    """Format seconds as MM:SS string
    Accepts int or float, rounds to int for display"""
    if isinstance(seconds, float):
        seconds = int(round(seconds))
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"

def get_audio_duration_ffprobe(file_path):
    """Get precise audio duration using ffprobe (more accurate than mutagen)
    Returns duration as float for maximum precision"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration_float = float(result.stdout.strip())
        return duration_float  # Return as float for maximum precision
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None

def extract_audio_metadata(file_path, m3u_base_dir=None):
    """Extract metadata from audio file using mutagen"""
    if not MUTAGEN_AVAILABLE:
        return None
    
    # Resolve file path (handle relative paths in m3u)
    if not os.path.isabs(file_path) and m3u_base_dir:
        file_path = os.path.join(m3u_base_dir, file_path)
    
    # Normalize path
    file_path = os.path.normpath(file_path)
    
    if not os.path.isfile(file_path):
        return None
    
    try:
        audio_file = File(file_path)
        if audio_file is None:
            return None
        
        metadata = {}
        
        # Helper function to safely get tag value
        def get_tag_value(tags, *keys):
            """Try multiple tag keys and return first found value"""
            for key in keys:
                if key in tags:
                    value = tags[key]
                    # Handle list values (common in mutagen)
                    if isinstance(value, list) and len(value) > 0:
                        return str(value[0]).strip()
                    elif value:
                        return str(value).strip()
            return None
        
        # Extract title - try various tag formats
        metadata['title'] = get_tag_value(
            audio_file,
            'TIT2',      # ID3v2.3/2.4 (MP3)
            'TITLE',     # Vorbis comment (FLAC/OGG)
            '\xa9nam',   # iTunes/M4A (MP4)
            '©nam'       # Alternative M4A format
        )
        
        # Extract artist
        metadata['artist'] = get_tag_value(
            audio_file,
            'TPE1',      # ID3v2.3/2.4 (MP3)
            'ARTIST',    # Vorbis comment (FLAC/OGG)
            '\xa9ART',   # iTunes/M4A (MP4)
            '©ART'       # Alternative M4A format
        )
        
        # Extract album
        metadata['album'] = get_tag_value(
            audio_file,
            'TALB',      # ID3v2.3/2.4 (MP3)
            'ALBUM',     # Vorbis comment (FLAC/OGG)
            '\xa9alb',   # iTunes/M4A (MP4)
            '©alb'       # Alternative M4A format
        )
        
        # Extract duration (in seconds)
        # Try ffprobe first for most accurate duration, fall back to mutagen
        duration = get_audio_duration_ffprobe(file_path)
        if duration is None:
            # Fall back to mutagen if ffprobe fails
            if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
                duration = float(audio_file.info.length)  # Keep as float
            else:
                duration = None
        
        if duration is not None:
            metadata['duration_seconds'] = duration  # Store as float
            metadata['length'] = format_length(int(duration))  # Round only for display
        else:
            metadata['duration_seconds'] = None
            metadata['length'] = None
        
        return metadata
        
    except Exception as e:
        # Silently fail - return None if we can't read the file
        return None

def parse_m3u(m3u_path):
    """Parse an m3u playlist file and return list of track dictionaries"""
    tracks = []
    
    with open(m3u_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for #EXTINF line
        if line.startswith('#EXTINF:'):
            # Format: #EXTINF:duration,display_name
            # Example: #EXTINF:123,Artist - Title
            match = re.match(r'#EXTINF:(\d+),?(.*)', line)
            if match:
                duration_seconds = int(match.group(1))
                display_name = match.group(2).strip() if match.group(2) else ""
                
                # Try to extract artist and title from display name
                # Common formats: "Artist - Title", "Artist / Title", "Title - Artist"
                artist = ""
                title = display_name
                album = ""
                
                # Try "Artist - Title" format (most common)
                if ' - ' in display_name:
                    parts = display_name.split(' - ', 1)
                    artist = parts[0].strip()
                    title = parts[1].strip() if len(parts) > 1 else display_name
                elif ' / ' in display_name:
                    parts = display_name.split(' / ', 1)
                    artist = parts[0].strip()
                    title = parts[1].strip() if len(parts) > 1 else display_name
                
                # Look for file path on next line
                file_path = ""
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith('#'):
                        file_path = next_line
                        i += 1
                
                # Generate uniqueId from file path or title
                unique_id = ""
                if file_path:
                    # Use filename without extension as uniqueId
                    unique_id = os.path.splitext(os.path.basename(file_path))[0]
                else:
                    # Fallback to title if no file path
                    unique_id = title.replace(' ', '_')[:128]
                
                track = {
                    'title': title[:128] if title else "",
                    'artist': artist[:128] if artist else "",
                    'album': album[:128] if album else "",
                    'length': format_length(duration_seconds),  # Display format (rounded)
                    'duration_seconds': float(duration_seconds),  # Store as float for precision
                    'uniqueId': unique_id[:128],
                    'artworkUrl': "",
                    'ignore': False,
                    'file_path': file_path  # Store file path for metadata extraction
                }
                
                tracks.append(track)
        
        i += 1
    
    return tracks

def concatenate_audio_files(tracks, m3u_base_dir, output_path):
    """Concatenate all audio files from tracks into a single MP3 using ffmpeg"""
    
    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg not found. Please install ffmpeg to use audio concatenation.")
        print("  Install with: brew install ffmpeg")
        return False
    
    # Collect valid file paths with absolute paths
    valid_files = []
    missing_files = []
    for i, track in enumerate(tracks, 1):
        if not track.get('file_path'):
            print(f"Warning [{i}]: No file path for track '{track['title']}', skipping")
            missing_files.append(i)
            continue
        
        # Resolve file path (handle relative paths in m3u)
        file_path = track['file_path']
        original_path = file_path
        
        if not os.path.isabs(file_path):
            file_path = os.path.join(m3u_base_dir, file_path)
        
        # Normalize and get absolute path
        file_path = os.path.normpath(file_path)
        file_path = os.path.abspath(file_path)
        
        if not os.path.isfile(file_path):
            print(f"Warning [{i}]: File not found")
            print(f"  Original path: {original_path}")
            print(f"  Resolved path: {file_path}")
            print(f"  Track: {track['artist']} - {track['title']}")
            missing_files.append(i)
            continue
        
        # Verify file is readable
        if not os.access(file_path, os.R_OK):
            print(f"Warning [{i}]: File not readable: {file_path}")
            print(f"  Track: {track['artist']} - {track['title']}")
            missing_files.append(i)
            continue
        
        valid_files.append(file_path)
    
    if not valid_files:
        print("Error: No valid audio files found to concatenate")
        return False
    
    if missing_files:
        print(f"\nWarning: {len(missing_files)} tracks will be skipped due to missing files")
    
    print(f"\nConcatenating {len(valid_files)} audio files into: {output_path}")
    print(f"Total tracks in playlist: {len(tracks)}")
    
    # Create a temporary file list for ffmpeg concat demuxer
    # Format: file 'path/to/file1.mp3'
    #         file 'path/to/file2.mp3'
    # Use absolute paths and proper escaping
    # For ffmpeg concat format, escape single quotes as '\''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        concat_list_path = f.name
        for file_path in valid_files:
            # Escape single quotes: ' becomes '\'' in the concat file
            # In Python string: '\\'' writes '\'' to the file
            escaped_path = file_path.replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
        f.flush()  # Ensure all data is written
        os.fsync(f.fileno())  # Force write to disk
    
    # Debug: print first few entries
    print(f"\nConcat list file: {concat_list_path}")
    print("First 3 entries in concat list:")
    with open(concat_list_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f.readlines()[:3], 1):
            print(f"  {i}: {line.strip()}")
    
    try:
        # Use concat filter instead of concat demuxer for better mixed format support
        # The concat demuxer can fail silently with mixed formats (MP3, M4A, etc.)
        # Build filter_complex that handles each file individually
        print("\nBuilding ffmpeg command for mixed audio formats...")
        
        # Create input arguments and filter for each file
        inputs = []
        filter_parts = []
        
        for i, file_path in enumerate(valid_files):
            inputs.extend(['-i', file_path])
            filter_parts.append(f"[{i}:a]")
        
        # Create concat filter: [0:a][1:a][2:a]...concat=n=N:v=0:a=1[out]
        filter_complex = ''.join(filter_parts) + f"concat=n={len(valid_files)}:v=0:a=1[out]"
        
        cmd = [
            'ffmpeg',
        ] + inputs + [
            '-filter_complex', filter_complex,
            '-map', '[out]',
            '-c:a', 'libmp3lame',  # Encode to MP3
            '-b:a', '320k',  # Bitrate
            '-y',  # Overwrite output file if it exists
            output_path
        ]
        
        print("\nRunning ffmpeg (re-encoding to MP3)...")
        print(f"Processing {len(valid_files)} files (mixed formats) - this may take a while...")
        
        # Run ffmpeg and capture output
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"\nError: ffmpeg failed with return code {result.returncode}")
            if result.stderr:
                # Look for specific error patterns
                stderr_lines = result.stderr.split('\n')
                
                # Find errors about specific files
                file_errors = []
                for i, line in enumerate(stderr_lines):
                    if 'error' in line.lower() or 'failed' in line.lower() or 'cannot' in line.lower():
                        # Try to find which file caused the error
                        if i > 0 and 'file' in stderr_lines[i-1].lower():
                            file_errors.append(f"  {stderr_lines[i-1].strip()}")
                        file_errors.append(f"  {line.strip()}")
                
                if file_errors:
                    print("\nFile-specific errors:")
                    for err in file_errors[:10]:  # Show first 10 errors
                        print(err)
                
                # Show last 20 lines for context
                print("\nLast 20 lines of ffmpeg stderr:")
                for line in stderr_lines[-20:]:
                    if line.strip():
                        print(f"  {line}")
            return False
        
        # Check output file was created and has reasonable size
        if os.path.isfile(output_path):
            file_size = os.path.getsize(output_path)
            print(f"\nSuccessfully created: {output_path}")
            print(f"Output file size: {file_size / (1024*1024):.2f} MB")
        else:
            print(f"\nWarning: Output file was not created: {output_path}")
            return False
        
        return True
        
    finally:
        # Clean up temporary file list
        try:
            os.unlink(concat_list_path)
        except OSError:
            pass

def import_m3u_to_db(tracks, m3u_path, episode_number, start_datetime, db_path, cover_image_base_url=None):
    """Import tracks from m3u file into database"""
    
    if not tracks:
        print("Error: No tracks found in m3u file")
        return False
    
    print(f"Found {len(tracks)} tracks")
    
    # Generate artwork URL from start datetime (similar to trackupdate.py)
    artwork_url = ""
    if cover_image_base_url:
        artwork_filename = start_datetime.strftime("%Y%m%d.jpg")
        artwork_url = f"{cover_image_base_url}/{artwork_filename}"
        print(f"Using artwork URL: {artwork_url}")
    
    # Extract metadata from audio files
    m3u_base_dir = os.path.dirname(os.path.abspath(m3u_path))
    print(f"\nExtracting metadata from audio files...")
    
    metadata_extracted = 0
    duration_updates = 0
    for track in tracks:
        original_duration = track['duration_seconds']
        if track['file_path']:
            # Resolve file path for duration check
            file_path = track['file_path']
            if not os.path.isabs(file_path):
                file_path = os.path.join(m3u_base_dir, file_path)
            file_path = os.path.normpath(os.path.abspath(file_path))
            
            # Get accurate duration using ffprobe (most accurate)
            if os.path.isfile(file_path):
                accurate_duration = get_audio_duration_ffprobe(file_path)
                if accurate_duration is not None:
                    track['duration_seconds'] = accurate_duration
                    track['length'] = format_length(accurate_duration)
                    if original_duration != track['duration_seconds']:
                        duration_updates += 1
            
            # Also extract metadata for title, artist, album
            metadata = extract_audio_metadata(track['file_path'], m3u_base_dir)
            if metadata:
                # Prefer file metadata over m3u data for title, artist, and album
                if metadata.get('title'):
                    track['title'] = metadata['title'][:128]
                if metadata.get('artist'):
                    track['artist'] = metadata['artist'][:128]
                if metadata.get('album'):
                    track['album'] = metadata['album'][:128]
                # Note: duration already set above using ffprobe
                metadata_extracted += 1
        
        # Set artwork URL for all tracks
        if artwork_url:
            track['artworkUrl'] = artwork_url
    
    if duration_updates > 0:
        print(f"Updated {duration_updates} track durations using ffprobe (accurate file durations)")
    
    if metadata_extracted > 0:
        print(f"Extracted metadata from {metadata_extracted} audio files")
    elif MUTAGEN_AVAILABLE:
        print("Warning: No audio file metadata could be extracted (files may not exist or be readable)")
    else:
        print("Warning: mutagen library not available - install with: pip install mutagen")
        print("         Continuing with m3u metadata only...")
    
    # Connect to database
    db_path = os.path.expanduser(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Ensure table exists
    c.execute('''
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
    # Add 0.5 second padding to all tracks except the first to account for concatenation delays
    CONCAT_PADDING = 0.0  # Half second padding for tracks after the first
    
    current_time = start_datetime
    inserted_count = 0
    
    print(f"\nImporting tracks starting at {start_datetime.isoformat()}")
    print(f"Applying {CONCAT_PADDING}s padding to tracks after the first (concatenation delay compensation)")
    print("-" * 80)
    
    for i, track in enumerate(tracks, 1):
        # Apply padding to all tracks except the first
        track_start_time = current_time
        if i > 1:
            track_start_time += timedelta(seconds=CONCAT_PADDING)
        
        # Insert track with calculated start time
        debool = 1 if track['ignore'] else 0
        c.execute("INSERT INTO trackupdate VALUES (?,?,?,?,?,?,?,?,?)",
                 (episode_number,
                  track['uniqueId'],
                  track['title'],
                  track['artist'],
                  track['album'],
                  track['length'],
                  track_start_time.isoformat(),
                  debool,
                  track['artworkUrl']))
        
        album_str = f" [{track['album']}]" if track['album'] else ""
        padding_note = f" (+{CONCAT_PADDING}s)" if i > 1 else ""
        print(f"{i:3d}. [{track_start_time.strftime('%H:%M:%S.%f')[:-3]}] {track['artist']} - {track['title']}{album_str} ({track['length']}){padding_note}")
        
        # Calculate next track start time (duration_seconds is float for precision)
        current_time += timedelta(seconds=track['duration_seconds'])
        inserted_count += 1
    
    conn.commit()
    conn.close()
    
    print("-" * 80)
    print(f"Successfully imported {inserted_count} tracks")
    print(f"Show ends at: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return True

def parse_datetime(datetime_str):
    """Parse datetime string in various formats, including subsecond precision"""
    formats = [
        '%Y-%m-%d %H:%M:%S.%f',  # With microseconds
        '%Y-%m-%d %H:%M:%S',      # Without microseconds
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S.%f',   # With microseconds
        '%Y/%m/%d %H:%M:%S',      # Without microseconds
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse datetime: {datetime_str}")

def main():
    parser = argparse.ArgumentParser(
        description='Import an m3u playlist into the trackupdate sqlite database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -f playlist.m3u -e 100 -d "2024-01-15 20:00:00"
  %(prog)s -f playlist.m3u -e 100 -d "2024-01-15 20:00:00.378297" --db ~/custom/path/db.sqlite
  %(prog)s -f playlist.m3u -e 100 -d "2024/01/15 20:00:00"
  %(prog)s -f playlist.m3u -e 100 -d "2024-01-15 20:00:00" -o output.mp3
        """
    )
    
    parser.add_argument('-f', '--file', required=True,
                       help='Path to m3u playlist file')
    parser.add_argument('-e', '--episode', required=True, type=int,
                       help='Episode number')
    parser.add_argument('-d', '--datetime', required=True,
                       help='Start date and time (format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD HH:MM:SS.ffffff)')
    parser.add_argument('--db',
                       help='Path to sqlite database (default: read from ~/.trackupdaterc)')
    parser.add_argument('--concat', '--output', '-o',
                       dest='output_mp3',
                       help='Output path for concatenated MP3 file (requires ffmpeg)')
    
    args = parser.parse_args()
    
    # Check if m3u file exists
    if not os.path.isfile(args.file):
        print(f"Error: m3u file not found: {args.file}")
        sys.exit(1)
    
    # Parse start datetime
    try:
        start_datetime = parse_datetime(args.datetime)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Read config file for database path and cover image settings
    config_path = os.path.expanduser('~/.trackupdaterc')
    config = None
    db_path = args.db
    cover_image_base_url = None
    
    if os.path.isfile(config_path):
        config = configparser.ConfigParser()
        config.read(config_path)
        
        # Get database path from config if not provided via CLI
        if not db_path:
            try:
                db_path = config.get('SqliteTarget', 'dbPath')
            except (configparser.NoSectionError, configparser.NoOptionError):
                print("Error: No database path specified and not found in ~/.trackupdaterc")
                print("Please specify --db or configure SqliteTarget.dbPath in ~/.trackupdaterc")
                sys.exit(1)
        
        # Get cover image base URL from config
        try:
            cover_image_base_url = config.get('trackupdate', 'coverImageBaseURL')
        except (configparser.NoSectionError, configparser.NoOptionError):
            # Not required, so just continue without it
            pass
    else:
        if not db_path:
            print("Error: No database path specified and ~/.trackupdaterc not found")
            print("Please specify --db or create ~/.trackupdaterc with SqliteTarget.dbPath")
            sys.exit(1)
    
    # Parse m3u file to get tracks (needed for both import and concatenation)
    print(f"Parsing m3u file: {args.file}")
    m3u_base_dir = os.path.dirname(os.path.abspath(args.file))
    tracks = parse_m3u(args.file)
    
    if not tracks:
        print("Error: No tracks found in m3u file")
        sys.exit(1)
    
    # Concatenate audio files if requested
    if args.output_mp3:
        output_path = os.path.expanduser(args.output_mp3)
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        concat_success = concatenate_audio_files(tracks, m3u_base_dir, output_path)
        if not concat_success:
            sys.exit(1)
    
    # Import tracks to database
    success = import_m3u_to_db(tracks, args.file, args.episode, start_datetime, db_path, cover_image_base_url)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()

