// Track Editor JavaScript

let wavesurfer = null;
let regionsPlugin = null;
let currentEpisode = null;
let tracks = [];
let markers = [];
let audioUrl = null;
let firstTime = null;
let currentZoom = 20; // Default zoom level (pixels per second)
let isDraggingMarker = false; // Track if we're currently dragging a marker
let cascadeShiftMode = false; // When true, dragging a marker shifts all subsequent tracks

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeWaveform();
    loadEpisodes();
    setupEventListeners();
    
    // Watch for any audio elements being added and hide them immediately
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) { // Element node
                    if (node.tagName === 'AUDIO' || node.querySelectorAll) {
                        const audioElements = node.tagName === 'AUDIO' 
                            ? [node] 
                            : node.querySelectorAll('audio');
                        audioElements.forEach(audio => {
                            audio.style.cssText = 'display: none !important; visibility: hidden !important; position: absolute !important; width: 0 !important; height: 0 !important; opacity: 0 !important; pointer-events: none !important;';
                            audio.removeAttribute('controls');
                        });
                    }
                }
            });
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});

function initializeWaveform() {
    // Initialize regions plugin first if available
    // Try different ways the plugin might be exposed
    try {
        if (typeof WaveSurfer !== 'undefined') {
            if (WaveSurfer.Regions) {
                regionsPlugin = WaveSurfer.Regions.create({});
            } else if (window.WaveSurferRegions) {
                regionsPlugin = window.WaveSurferRegions.create({});
            } else if (typeof Regions !== 'undefined') {
                regionsPlugin = Regions.create({});
            } else {
                console.warn('Regions plugin not found. Available:', Object.keys(window).filter(k => k.toLowerCase().includes('region')));
            }
        }
    } catch (e) {
        console.error('Error initializing regions plugin:', e);
    }
    
    const config = {
        container: '#waveform',
        waveColor: '#4a90e2',
        progressColor: '#357abd',
        cursorColor: '#357abd',
        barWidth: 2,
        barRadius: 3,
        responsive: false, // Disable responsive to allow fixed width with scrolling
        height: 128,
        normalize: true,
        minPxPerSec: currentZoom,
        fillParent: false, // Don't fill parent, let it be wider when zoomed
        interact: true, // Enable interaction for scrolling
        backend: 'WebAudio' // Use WebAudio backend instead of MediaElement to avoid HTML5 audio element
    };
    
    if (regionsPlugin) {
        config.plugins = [regionsPlugin];
    }
    
    wavesurfer = WaveSurfer.create(config);

    wavesurfer.on('ready', () => {
        // Hide/remove any audio elements that WaveSurfer creates internally
        const hideAudioElements = () => {
            const audioElements = document.querySelectorAll('audio');
            audioElements.forEach(audio => {
                // Try to get the media element from WaveSurfer and hide it
                if (wavesurfer.getMediaElement && wavesurfer.getMediaElement()) {
                    const mediaEl = wavesurfer.getMediaElement();
                    mediaEl.style.cssText = 'display: none !important; visibility: hidden !important; position: absolute !important; width: 0 !important; height: 0 !important; opacity: 0 !important; pointer-events: none !important;';
                    mediaEl.removeAttribute('controls');
                }
                // Also hide any other audio elements
                audio.style.cssText = 'display: none !important; visibility: hidden !important; position: absolute !important; width: 0 !important; height: 0 !important; opacity: 0 !important; pointer-events: none !important;';
                audio.removeAttribute('controls');
            });
        };
        
        // Hide immediately and also after a short delay
        hideAudioElements();
        setTimeout(hideAudioElements, 100);
        setTimeout(hideAudioElements, 500);
        
        updateTimeDisplay();
        // Update markers when audio is ready
        if (tracks.length > 0) {
            updateWaveformMarkers();
        }
        
        // Disable click-and-drag scrolling on waveform container
        // Only allow scrollbar scrolling
        const container = document.querySelector('.waveform-container');
        const waveformElement = document.querySelector('#waveform');
        
        if (container && waveformElement) {
            let isMouseDown = false;
            let startX = 0;
            let scrollLeft = 0;
            
            // Only prevent scrolling when clicking directly on the waveform, not on scrollbar
            waveformElement.addEventListener('mousedown', (e) => {
                // Don't prevent if clicking on a region/marker
                const target = e.target;
                if (!target.closest('.wavesurfer-region') && 
                    !target.closest('[data-resize-handle]') &&
                    e.button === 0) { // Left mouse button only
                    isMouseDown = true;
                    startX = e.pageX;
                    scrollLeft = container.scrollLeft;
                    e.preventDefault();
                    e.stopPropagation();
                }
            });
            
            document.addEventListener('mousemove', (e) => {
                if (!isMouseDown) return;
                e.preventDefault();
                const walk = (e.pageX - startX);
                container.scrollLeft = scrollLeft - walk;
            });
            
            document.addEventListener('mouseup', () => {
                isMouseDown = false;
            });
        }
    });

    wavesurfer.on('audioprocess', () => {
        updateTimeDisplay();
        // Auto-scroll to keep cursor visible when playing
        if (wavesurfer.isPlaying()) {
            scrollToCurrentPosition();
        }
    });

    wavesurfer.on('play', () => {
        document.getElementById('playPauseBtn').textContent = 'Pause';
    });

    wavesurfer.on('pause', () => {
        document.getElementById('playPauseBtn').textContent = 'Play';
    });

    wavesurfer.on('finish', () => {
        document.getElementById('playPauseBtn').textContent = 'Play';
    });
}

function setupEventListeners() {
    // Episode selection
    document.getElementById('episodeSelect').addEventListener('change', (e) => {
        if (e.target.value) {
            currentEpisode = parseInt(e.target.value);
            loadTracks(currentEpisode);
        }
    });

    // New episode button
    document.getElementById('newEpisodeBtn').addEventListener('click', () => {
        const epNum = prompt('Enter episode number:');
        if (epNum) {
            currentEpisode = parseInt(epNum);
            document.getElementById('episodeSelect').value = epNum;
            tracks = [];
            renderTracks();
        }
    });

    // Delete episode button
    document.getElementById('deleteEpisodeBtn').addEventListener('click', () => {
        deleteEpisode();
    });

    // File upload
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');

    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Change audio file button
    document.getElementById('changeAudioBtn').addEventListener('click', () => {
        document.getElementById('dropZone').style.display = 'block';
        document.getElementById('audioInfo').style.display = 'none';
        document.getElementById('uploadSection').classList.remove('collapsed');
        audioUrl = null;
        if (wavesurfer) {
            wavesurfer.empty();
        }
    });

    // Toggle upload section
    document.getElementById('toggleUploadSection').addEventListener('click', () => {
        const section = document.getElementById('uploadSection');
        const toggleBtn = document.getElementById('toggleUploadSection');
        section.classList.toggle('collapsed');
        toggleBtn.textContent = section.classList.contains('collapsed') ? '+' : '−';
    });

    // Waveform controls
    document.getElementById('playPauseBtn').addEventListener('click', () => {
        if (wavesurfer) {
            wavesurfer.playPause();
        }
    });

    document.getElementById('zoomInBtn').addEventListener('click', () => {
        if (wavesurfer && wavesurfer.getDuration()) {
            currentZoom = Math.min(currentZoom * 1.5, 500); // Max zoom
            wavesurfer.zoom(currentZoom);
            // Update markers after zoom
            if (tracks.length > 0) {
                updateWaveformMarkers();
            }
        }
    });

    document.getElementById('zoomOutBtn').addEventListener('click', () => {
        if (wavesurfer && wavesurfer.getDuration()) {
            currentZoom = Math.max(currentZoom / 1.5, 1); // Min zoom
            wavesurfer.zoom(currentZoom);
            // Update markers after zoom
            if (tracks.length > 0) {
                updateWaveformMarkers();
            }
        }
    });

    // Track controls
    document.getElementById('addTrackBtn').addEventListener('click', () => {
        if (!currentEpisode) {
            alert('Please select an episode first');
            return;
        }
        openTrackModal();
    });

    // Insert track at cursor position
    document.getElementById('insertTrackAtCursorBtn').addEventListener('click', () => {
        if (!currentEpisode) {
            alert('Please select an episode first');
            return;
        }
        if (!wavesurfer || !wavesurfer.getDuration()) {
            alert('Please load an audio file first');
            return;
        }
        const currentTime = wavesurfer.getCurrentTime();
        openTrackModal(null, currentTime);
    });

    document.getElementById('shiftTracksBtn').addEventListener('click', () => {
        openShiftModal();
    });

    document.getElementById('selectAllTracksBtn').addEventListener('click', () => {
        selectAllTracks();
    });

    document.getElementById('clearSelectionBtn').addEventListener('click', () => {
        clearSelection();
    });

    // Import M3U button
    document.getElementById('importM3uBtn').addEventListener('click', () => {
        openImportM3uModal();
    });

    // Export/Import Episode buttons
    document.getElementById('exportEpisodeBtn').addEventListener('click', () => {
        exportEpisode();
    });

    document.getElementById('importEpisodeBtn').addEventListener('click', () => {
        openImportEpisodeModal();
    });

    // Cascade shift mode toggle
    document.getElementById('cascadeShiftMode').addEventListener('change', (e) => {
        cascadeShiftMode = e.target.checked;
    });

    // Modal controls
    document.querySelectorAll('.close').forEach(closeBtn => {
        closeBtn.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
                // Clear import status
                const statusDiv = document.getElementById('importStatus');
                if (statusDiv) {
                    statusDiv.style.display = 'none';
                }
            }
        });
    });

    document.getElementById('cancelBtn').addEventListener('click', () => {
        document.getElementById('trackModal').style.display = 'none';
    });

    document.getElementById('cancelShiftBtn').addEventListener('click', () => {
        document.getElementById('shiftModal').style.display = 'none';
    });

    document.getElementById('cancelImportBtn').addEventListener('click', () => {
        document.getElementById('importM3uModal').style.display = 'none';
        document.getElementById('importStatus').style.display = 'none';
    });

    document.getElementById('trackForm').addEventListener('submit', (e) => {
        e.preventDefault();
        saveTrack();
    });

    document.getElementById('shiftForm').addEventListener('submit', (e) => {
        e.preventDefault();
        shiftTracks();
    });

    document.getElementById('importM3uForm').addEventListener('submit', (e) => {
        e.preventDefault();
        importM3u();
    });

    document.getElementById('importEpisodeForm').addEventListener('submit', (e) => {
        e.preventDefault();
        importEpisode();
    });
}

async function loadEpisodes() {
    try {
        const response = await fetch('/api/episodes');
        
        if (!response.ok) {
            console.error('Error loading episodes:', response.status, response.statusText);
            return;
        }
        
        const episodes = await response.json();
        
        if (!Array.isArray(episodes)) {
            console.error('Invalid response format:', episodes);
            return;
        }
        
        const select = document.getElementById('episodeSelect');
        
        // Clear existing options except the first one
        while (select.options.length > 1) {
            select.remove(1);
        }
        
        if (episodes.length === 0) {
            console.log('No episodes found in database');
            return;
        }
        
        episodes.forEach(ep => {
            const option = document.createElement('option');
            option.value = ep;
            option.textContent = `Episode ${ep}`;
            select.appendChild(option);
        });
        
        console.log(`Loaded ${episodes.length} episodes`);
    } catch (error) {
        console.error('Error loading episodes:', error);
        alert('Error loading episodes: ' + error.message);
    }
}

async function deleteEpisode() {
    if (!currentEpisode) {
        alert('Please select an episode to delete');
        return;
    }
    
    const episodeToDelete = currentEpisode;
    const confirmed = confirm(`Are you sure you want to delete Episode ${episodeToDelete}? This will permanently delete all tracks for this episode.`);
    
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await fetch(`/api/episodes/${episodeToDelete}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            // Clear current episode and tracks
            currentEpisode = null;
            tracks = [];
            document.getElementById('episodeSelect').value = '';
            renderTracks();
            
            // Reload episodes list to remove the deleted episode
            await loadEpisodes();
            
            alert(`Episode ${episodeToDelete} has been deleted`);
        } else {
            const error = await response.json();
            alert('Error deleting episode: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting episode:', error);
        alert('Error deleting episode: ' + error.message);
    }
}

async function loadTracks(episodeNumber, preserveScroll = false) {
    try {
        // Save scroll position if requested
        const container = document.querySelector('.waveform-container');
        let savedScrollLeft = 0;
        if (preserveScroll && container) {
            savedScrollLeft = container.scrollLeft;
        }
        
        const response = await fetch(`/api/episodes/${episodeNumber}/tracks`);
        const data = await response.json();
        
        // Sort tracks by startTimeSeconds to ensure correct order
        tracks = data.tracks.sort((a, b) => {
            const timeA = a.startTimeSeconds || 0;
            const timeB = b.startTimeSeconds || 0;
            return timeA - timeB;
        });
        
        firstTime = data.firstTime ? new Date(data.firstTime) : null;
        
        renderTracks();
        // Only update markers if audio is loaded
        if (wavesurfer && wavesurfer.getDuration() > 0) {
            updateWaveformMarkers();
            
            // Restore scroll position after markers are updated
            if (preserveScroll && container) {
                // Use requestAnimationFrame to ensure markers are rendered
                requestAnimationFrame(() => {
                    container.scrollLeft = savedScrollLeft;
                });
            }
        }
    } catch (error) {
        console.error('Error loading tracks:', error);
        alert('Error loading tracks: ' + error.message);
    }
}

// Track selection state
let lastSelectedIndex = null;

function renderTracks() {
    const tracksList = document.getElementById('tracksList');
    tracksList.innerHTML = '';
    lastSelectedIndex = null; // Reset last selected when tracks are re-rendered

    tracks.forEach((track, index) => {
        const trackDiv = document.createElement('div');
        trackDiv.className = `track-item ${track.ignore ? 'ignored' : ''}`;
        trackDiv.dataset.index = index;
        
        const timeStr = formatTime(track.startTimeSeconds);
        const lengthStr = track.length || '0:00';
        
        trackDiv.innerHTML = `
            <div class="track-header">
                <label class="track-checkbox-label">
                    <input type="checkbox" class="track-checkbox" data-index="${index}">
                    <span class="track-number">${index + 1}</span>
                </label>
                <span class="track-time">${timeStr}</span>
                <span class="track-title">${track.title || 'Untitled'}</span>
                <span class="track-artist">${track.artist || 'Unknown'}</span>
            </div>
            <div class="track-details">
                <span>Length: ${lengthStr}</span>
                <span>Album: ${track.album || 'N/A'}</span>
            </div>
            <div class="track-actions">
                <button onclick="editTrack(${index})">Edit</button>
                <button onclick="deleteTrack(${index})">Delete</button>
                <button onclick="seekToTrack(${index})">Go To</button>
            </div>
        `;
        
        tracksList.appendChild(trackDiv);
    });
    
    // Add event listeners for range selection
    setupCheckboxListeners();
    updateShiftButtonState();
}

function setupCheckboxListeners() {
    const checkboxes = document.querySelectorAll('.track-checkbox');
    let isRangeSelecting = false;
    
    checkboxes.forEach((checkbox) => {
        // Prevent click event first (with capture phase to catch it early)
        checkbox.addEventListener('click', (e) => {
            if (isRangeSelecting) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                return false;
            }
        }, true); // Use capture phase
        
        // Use mousedown to catch before checkbox toggles
        checkbox.addEventListener('mousedown', (e) => {
            const currentIndex = parseInt(checkbox.dataset.index);
            const isShiftPressed = e.shiftKey;
            
            if (isShiftPressed && lastSelectedIndex !== null) {
                // Range selection: select all from lastSelectedIndex to currentIndex (inclusive)
                e.preventDefault();
                e.stopPropagation();
                isRangeSelecting = true;
                
                const minIndex = Math.min(lastSelectedIndex, currentIndex);
                const maxIndex = Math.max(lastSelectedIndex, currentIndex);
                const allCheckboxes = document.querySelectorAll('.track-checkbox');

                const sortedCheckboxes = Array.prototype.slice.call(allCheckboxes, 0);
                sortedCheckboxes.sort((a, b) => parseInt(a.dataset.index) - parseInt(b.dataset.index));
                
                for (let i = minIndex; i <= maxIndex; i++) {
                    const cb = sortedCheckboxes[i];
                    cb.checked = true;
                }
            } else {
                // Regular click: update lastSelectedIndex, let default behavior happen
                lastSelectedIndex = currentIndex;
                isRangeSelecting = false;
            }
        });
        
        // Store the expected state during range selection
        let expectedCheckedState = null;
        
        // Update button state on change (but skip during range selection)
        checkbox.addEventListener('change', (e) => {
            if (isRangeSelecting && expectedCheckedState !== null) {
                // During range selection, revert to expected state
                checkbox.checked = expectedCheckedState;
            } else {
                updateShiftButtonState();
            }
        });
    });
}

function getSelectedTrackIndices() {
    const checkboxes = document.querySelectorAll('.track-checkbox:checked');
    return Array.from(checkboxes).map(cb => parseInt(cb.dataset.index)).sort((a, b) => a - b);
}

function updateShiftButtonState() {
    const selectedIndices = getSelectedTrackIndices();
    const shiftBtn = document.getElementById('shiftTracksBtn');
    if (shiftBtn) {
        if (selectedIndices.length > 0) {
            shiftBtn.textContent = `Shift Selected (${selectedIndices.length})`;
            shiftBtn.disabled = false;
        } else {
            shiftBtn.textContent = 'Shift Selected';
            shiftBtn.disabled = false;
        }
    }
}

function selectAllTracks() {
    const checkboxes = document.querySelectorAll('.track-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = true;
    });
    updateShiftButtonState();
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('.track-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    updateShiftButtonState();
}

function updateWaveformMarkers() {
    if (!wavesurfer || !audioUrl) return;
    
    const duration = wavesurfer.getDuration();
    if (!duration || duration === 0) {
        // Audio not ready yet, wait for ready event
        console.log('Audio not ready, duration:', duration);
        return;
    }

    // Clear existing regions/markers
    if (regionsPlugin) {
        try {
            regionsPlugin.clearRegions();
        } catch (e) {
            console.error('Error clearing regions:', e);
        }
    }
    markers = [];

    console.log(`Adding markers for ${tracks.length} tracks, duration: ${duration}`);

    // Add thin vertical markers (separators) at track start positions
    tracks.forEach((track, index) => {
        if (track.startTimeSeconds !== undefined && track.startTimeSeconds >= 0) {
            const startTime = track.startTimeSeconds;
            
            // Only add if within audio duration
            if (startTime < duration) {
                if (regionsPlugin) {
                    try {
                        // Create a very thin region (0.1 seconds) to act as a vertical line marker
                        const markerWidth = 0.1; // Very thin - just a vertical line
                        const region = regionsPlugin.addRegion({
                            start: startTime,
                            content: track.title,
                            color: track.ignore ? 'rgba(255, 107, 107, 0.3)' : 'rgba(74, 144, 226, 0.3)',
                            drag: true,
                            resize: false
                        });

                        // Store track index with region for reference
                        region.trackIndex = index;
                        let originalStartTime = startTime; // Store original time for delta calculation
                        
                        // Track when dragging starts
                        region.on('update', () => {
                            isDraggingMarker = true;
                        });
                        
                        // Update track time when marker is dragged
                        region.on('update-end', () => {
                            const newTime = region.start;
                            const deltaSeconds = newTime - originalStartTime;
                            isDraggingMarker = false;
                            
                            if (cascadeShiftMode && deltaSeconds !== 0) {
                                // Shift this track and all subsequent tracks
                                updateTrackTimeWithCascade(index, newTime, deltaSeconds);
                            } else {
                                // Just update this track
                                updateTrackTime(index, newTime);
                            }
                            
                            // Update original time for next drag
                            originalStartTime = newTime;
                        });

                        markers.push(region);
                        console.log(`Added marker for track ${index} at ${startTime}s`);
                    } catch (e) {
                        console.error('Error adding marker:', e, track);
                    }
                } else {
                    console.warn('Regions plugin not available, cannot add markers');
                }
            } else {
                console.log(`Track ${index} start time ${startTime}s is beyond duration ${duration}s`);
            }
        }
    });
}

async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (data.success) {
            audioUrl = data.url;
            document.getElementById('fileName').textContent = file.name;
            document.getElementById('audioInfo').style.display = 'block';
            document.getElementById('dropZone').style.display = 'none';
            document.getElementById('toggleUploadSection').style.display = 'block';
            
            // Collapse the upload section after file is loaded
            document.getElementById('uploadSection').classList.add('collapsed');
            
            // Load audio into wavesurfer
            wavesurfer.load(audioUrl).then(() => {
                // Hide any audio elements after loading
                setTimeout(() => {
                    const audioElements = document.querySelectorAll('audio');
                    audioElements.forEach(audio => {
                        audio.style.cssText = 'display: none !important; visibility: hidden !important; position: absolute !important; width: 0 !important; height: 0 !important; opacity: 0 !important; pointer-events: none !important;';
                        audio.removeAttribute('controls');
                    });
                }, 100);
                
                // Set initial zoom after loading
                if (wavesurfer.getDuration()) {
                    wavesurfer.zoom(currentZoom);
                }
                // Markers will be added in the 'ready' event handler
                // But also update them here in case tracks are already loaded
                if (tracks.length > 0) {
                    updateWaveformMarkers();
                }
            });
        } else {
            alert('Error uploading file: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error uploading file:', error);
        alert('Error uploading file: ' + error.message);
    }
}

function openTrackModal(trackIndex = null, startTimeSeconds = null) {
    const modal = document.getElementById('trackModal');
    const form = document.getElementById('trackForm');
    
    if (trackIndex !== null) {
        const track = tracks[trackIndex];
        document.getElementById('modalTitle').textContent = 'Edit Track';
        document.getElementById('trackId').value = track.id;
        document.getElementById('trackTitle').value = track.title || '';
        document.getElementById('trackArtist').value = track.artist || '';
        document.getElementById('trackAlbum').value = track.album || '';
        document.getElementById('trackLength').value = track.length || '0:00';
        document.getElementById('trackStartTime').value = track.startTimeSeconds || 0;
        document.getElementById('trackIgnore').checked = track.ignore || false;
    } else {
        document.getElementById('modalTitle').textContent = 'Add Track';
        form.reset();
        document.getElementById('trackId').value = '';
        
        // Set start time: use provided value, or current playback position, or 0
        let startTime = 0;
        if (startTimeSeconds !== null) {
            startTime = startTimeSeconds;
        } else if (wavesurfer) {
            startTime = wavesurfer.getCurrentTime() || 0;
        }
        document.getElementById('trackStartTime').value = startTime;
    }
    
    modal.style.display = 'block';
}

function editTrack(index) {
    openTrackModal(index);
}

async function saveTrack() {
    const form = document.getElementById('trackForm');
    const trackId = document.getElementById('trackId').value;
    const trackData = {
        uniqueId: trackId || null,
        title: document.getElementById('trackTitle').value,
        artist: document.getElementById('trackArtist').value,
        album: document.getElementById('trackAlbum').value,
        length: document.getElementById('trackLength').value,
        startTimeSeconds: parseFloat(document.getElementById('trackStartTime').value),
        ignore: document.getElementById('trackIgnore').checked,
        artworkUrl: ''
    };

    try {
        let response;
        const existingTrack = trackId ? tracks.find(t => t.id === trackId) : null;
        if (existingTrack) {
            // Update existing track
            response = await fetch(`/api/episodes/${currentEpisode}/tracks/${trackId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(trackData)
            });
        } else {
            // Create new track
            response = await fetch(`/api/episodes/${currentEpisode}/tracks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(trackData)
            });
        }

        if (response.ok) {
            document.getElementById('trackModal').style.display = 'none';
            await loadTracks(currentEpisode);
        } else {
            const error = await response.json();
            alert('Error saving track: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error saving track:', error);
        alert('Error saving track: ' + error.message);
    }
}

async function deleteTrack(index) {
    if (!confirm('Are you sure you want to delete this track?')) {
        return;
    }

    const track = tracks[index];
    
    try {
        const response = await fetch(`/api/episodes/${currentEpisode}/tracks/${track.id}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            await loadTracks(currentEpisode);
        } else {
            alert('Error deleting track');
        }
    } catch (error) {
        console.error('Error deleting track:', error);
        alert('Error deleting track: ' + error.message);
    }
}

function seekToTrack(index) {
    const track = tracks[index];
    if (wavesurfer && track.startTimeSeconds !== undefined) {
        const duration = wavesurfer.getDuration();
        if (duration && duration > 0 && track.startTimeSeconds < duration) {
            // Set the current time
            wavesurfer.setTime(track.startTimeSeconds);
            // Also seek to the position (normalized 0-1)
            wavesurfer.seekTo(track.startTimeSeconds / duration);
            // Start playing
            wavesurfer.play();
        }
    }
}

async function updateTrackTime(index, newTimeSeconds) {
    const track = tracks[index];
    const trackData = {
        uniqueId: track.uniqueId,
        title: track.title,
        artist: track.artist,
        album: track.album,
        length: track.length,
        startTimeSeconds: newTimeSeconds,
        ignore: track.ignore,
        artworkUrl: track.artworkUrl
    };

    try {
        const response = await fetch(`/api/episodes/${currentEpisode}/tracks/${track.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(trackData)
        });

        if (response.ok) {
            // Preserve scroll position when updating track time (from marker drag)
            await loadTracks(currentEpisode, true);
        }
    } catch (error) {
        console.error('Error updating track time:', error);
    }
}

async function updateTrackTimeWithCascade(startIndex, newStartTime, deltaSeconds) {
    // Update the dragged track first
    const startTrack = tracks[startIndex];
    const startTrackData = {
        uniqueId: startTrack.uniqueId,
        title: startTrack.title,
        artist: startTrack.artist,
        album: startTrack.album,
        length: startTrack.length,
        startTimeSeconds: newStartTime,
        ignore: startTrack.ignore,
        artworkUrl: startTrack.artworkUrl
    };

    try {
        // Update the first track
        const response = await fetch(`/api/episodes/${currentEpisode}/tracks/${startTrack.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(startTrackData)
        });

        if (response.ok && deltaSeconds !== 0) {
            // Shift all subsequent tracks by the same delta
            const shiftResponse = await fetch(`/api/episodes/${currentEpisode}/tracks/shift`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    startIndex: startIndex + 1, // Start from the track after the dragged one
                    endIndex: null, // Shift all remaining tracks
                    deltaSeconds: deltaSeconds
                })
            });

            if (shiftResponse.ok) {
                // Preserve scroll position when updating tracks
                await loadTracks(currentEpisode, true);
            }
        } else if (response.ok) {
            // No cascade needed, just reload
            await loadTracks(currentEpisode, true);
        }
    } catch (error) {
        console.error('Error updating track time with cascade:', error);
    }
}

function openShiftModal() {
    const selectedIndices = getSelectedTrackIndices();
    
    if (selectedIndices.length === 0) {
        alert('Please select at least one track to shift');
        return;
    }
    
    document.getElementById('shiftModal').style.display = 'block';
    document.getElementById('shiftDelta').value = '';
    
    // Update the modal to show selected tracks info
    const selectedInfo = document.getElementById('shiftSelectedInfo');
    if (selectedInfo) {
        selectedInfo.textContent = `Selected ${selectedIndices.length} track(s): ${selectedIndices.map(i => i + 1).join(', ')}`;
    }
}

async function shiftTracks() {
    const selectedIndices = getSelectedTrackIndices();
    
    if (selectedIndices.length === 0) {
        alert('Please select at least one track to shift');
        return;
    }
    
    // Backend uses exclusive end index, so we add 1 to the last selected index
    const startIndex = selectedIndices[0];
    const endIndex = selectedIndices[selectedIndices.length - 1] + 1; // Exclusive end for backend
    const deltaSeconds = parseFloat(document.getElementById('shiftDelta').value);

    if (isNaN(deltaSeconds)) {
        alert('Please enter a valid shift value');
        return;
    }

    try {
        const response = await fetch(`/api/episodes/${currentEpisode}/tracks/shift`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                startIndex: startIndex,
                endIndex: endIndex,
                deltaSeconds: deltaSeconds
            })
        });

        if (response.ok) {
            document.getElementById('shiftModal').style.display = 'none';
            // Clear selections after shift
            document.querySelectorAll('.track-checkbox').forEach(cb => cb.checked = false);
            updateShiftButtonState();
            await loadTracks(currentEpisode);
        } else {
            alert('Error shifting tracks');
        }
    } catch (error) {
        console.error('Error shifting tracks:', error);
        alert('Error shifting tracks: ' + error.message);
    }
}

function updateTimeDisplay() {
    if (!wavesurfer) return;
    
    const current = wavesurfer.getCurrentTime();
    const duration = wavesurfer.getDuration();
    
    document.getElementById('timeDisplay').textContent = 
        `${formatTime(current)} / ${formatTime(duration)}`;
}

function formatTime(seconds) {
    if (!seconds && seconds !== 0) return '0:00';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

function scrollToCurrentPosition() {
    if (!wavesurfer || isDraggingMarker) return; // Don't auto-scroll while dragging markers
    
    const container = document.querySelector('.waveform-container');
    if (!container) return;
    
    const currentTime = wavesurfer.getCurrentTime();
    const duration = wavesurfer.getDuration();
    if (!duration || duration === 0) return;
    
    // Calculate the pixel position of the current time
    const pixelsPerSecond = currentZoom;
    const currentPixel = currentTime * pixelsPerSecond;
    
    // Get container width
    const containerWidth = container.clientWidth;
    
    // Calculate scroll position to center the cursor
    const scrollPosition = currentPixel - (containerWidth / 2);
    
    // Only scroll if the cursor would be outside the visible area
    const currentScroll = container.scrollLeft;
    const scrollRight = currentScroll + containerWidth;
    
    if (currentPixel < currentScroll || currentPixel > scrollRight) {
        container.scrollLeft = Math.max(0, scrollPosition);
    }
}

function openImportM3uModal() {
    document.getElementById('importM3uModal').style.display = 'block';
    document.getElementById('importM3uForm').reset();
    document.getElementById('importStatus').style.display = 'none';
    
    // Pre-fill episode number if one is selected
    if (currentEpisode) {
        document.getElementById('importEpisodeNumber').value = currentEpisode;
    }
    
    // Pre-fill datetime with current time
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('importStartDatetime').value = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

async function importM3u() {
    const episodeNumber = document.getElementById('importEpisodeNumber').value;
    const startDatetime = document.getElementById('importStartDatetime').value;
    const fileInput = document.getElementById('importM3uFile');
    
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('Please select an M3U file');
        return;
    }
    
    const statusDiv = document.getElementById('importStatus');
    statusDiv.style.display = 'block';
    statusDiv.textContent = 'Importing...';
    statusDiv.className = 'import-status importing';
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('episodeNumber', episodeNumber);
    formData.append('startDatetime', startDatetime);
    
    try {
        const response = await fetch('/api/import/m3u', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            statusDiv.className = 'import-status success';
            statusDiv.innerHTML = `
                <strong>Import successful!</strong><br>
                ${data.tracksImported} tracks imported<br>
                ${data.metadataExtracted} tracks with metadata extracted<br>
                ${data.durationUpdates} durations updated
            `;
            
            // Close modal after a short delay and load the episode
            setTimeout(() => {
                document.getElementById('importM3uModal').style.display = 'none';
                currentEpisode = data.episodeNumber;
                document.getElementById('episodeSelect').value = data.episodeNumber;
                loadTracks(data.episodeNumber);
            }, 2000);
        } else {
            statusDiv.className = 'import-status error';
            statusDiv.textContent = 'Error: ' + (data.error || 'Unknown error');
        }
    } catch (error) {
        statusDiv.className = 'import-status error';
        statusDiv.textContent = 'Error: ' + error.message;
    }
}

function exportEpisode() {
    if (!currentEpisode) {
        alert('Please select an episode first');
        return;
    }

    if (tracks.length === 0) {
        alert('No tracks to export');
        return;
    }

    // Prepare export data
    const exportData = {
        episodeNumber: currentEpisode,
        firstTime: firstTime ? firstTime.toISOString() : null,
        tracks: tracks.map(track => ({
            uniqueId: track.uniqueId,
            title: track.title,
            artist: track.artist,
            album: track.album,
            length: track.length,
            startTimeSeconds: track.startTimeSeconds,
            ignore: track.ignore,
            artworkUrl: track.artworkUrl
        }))
    };

    // Create and download JSON file
    const dataStr = JSON.stringify(exportData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `episode-${currentEpisode}-tracks.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function openImportEpisodeModal() {
    document.getElementById('importEpisodeModal').style.display = 'block';
    document.getElementById('importEpisodeForm').reset();
    document.getElementById('importEpisodeStatus').style.display = 'none';
    
    // Pre-fill episode number if one is selected
    if (currentEpisode) {
        document.getElementById('importEpisodeDataNumber').value = currentEpisode;
    }
}

async function importEpisode() {
    const episodeNumber = document.getElementById('importEpisodeDataNumber').value;
    const fileInput = document.getElementById('importEpisodeFile');
    
    if (!episodeNumber) {
        alert('Please enter an episode number');
        return;
    }
    
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('Please select a JSON file');
        return;
    }

    if (!confirm(`This will replace all existing tracks for episode ${episodeNumber}. Continue?`)) {
        return;
    }
    
    const statusDiv = document.getElementById('importEpisodeStatus');
    statusDiv.style.display = 'block';
    statusDiv.textContent = 'Importing...';
    statusDiv.className = 'import-status importing';
    
    try {
        const file = fileInput.files[0];
        const text = await file.text();
        const data = JSON.parse(text);
        
        const response = await fetch(`/api/episodes/${episodeNumber}/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            statusDiv.className = 'import-status success';
            statusDiv.innerHTML = `
                <strong>Import successful!</strong><br>
                ${result.tracksImported} tracks imported
            `;
            
            // Close modal after a short delay and load the episode
            setTimeout(() => {
                document.getElementById('importEpisodeModal').style.display = 'none';
                currentEpisode = parseInt(episodeNumber);
                document.getElementById('episodeSelect').value = episodeNumber;
                loadTracks(currentEpisode);
            }, 2000);
        } else {
            statusDiv.className = 'import-status error';
            statusDiv.textContent = 'Error: ' + (result.error || 'Unknown error');
        }
    } catch (error) {
        statusDiv.className = 'import-status error';
        statusDiv.textContent = 'Error: ' + error.message;
    }
}

// Make functions available globally for onclick handlers
window.editTrack = editTrack;
window.deleteTrack = deleteTrack;
window.seekToTrack = seekToTrack;

