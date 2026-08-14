"""Precomputed waveform peaks for the web editor.

The editor used to hand the raw mp3 to WaveSurfer's WebAudio backend, which
decoded the whole file to Float32 PCM in the browser -- roughly 2.5 GB of heap
for a two hour show, plus a full pass over it to find peaks.

Instead we let ffmpeg decode to a low rate mono stream, reduce it to a min/max
envelope here, and cache the result. WaveSurfer skips decoding entirely when it
is given peaks and a duration, so repeat opens cost nothing.

Measured on a 2 h / 278 MB / 320 kbps show: ~8 s for the ffmpeg pass and ~1.7 s
for the bucketing (which overlaps with ffmpeg, since we stream its output).
"""

import hashlib
import os
import subprocess
import sys
import tempfile
from array import array

# Rate we ask ffmpeg to resample to. Low enough to keep the byte count sane,
# high enough that the anti-alias filter doesn't swallow percussion -- which
# matters, because near-silence is how you spot a track boundary.
DECODE_SAMPLE_RATE = 8000

# Envelope resolution. The editor's maximum zoom is 500 px/sec at barWidth 2
# (~250 bars/sec), so 100/sec upsamples slightly at full zoom -- imperceptible
# when what you're looking for is where the music stops.
PEAKS_PER_SECOND = 100

# Bytes pulled from ffmpeg per read. Multiple of 4 so it never splits a float.
_READ_CHUNK = 1 << 20


class PeaksUnavailable(Exception):
    """ffmpeg is missing or failed, so the caller should fall back."""


def _bucket(stream, samples_per_bucket):
    """Reduce a stream of f32le bytes to interleaved min/max pairs."""
    out = array('f')
    bucket_bytes = samples_per_bucket * 4
    pending = b''

    while True:
        chunk = stream.read(_READ_CHUNK)
        if not chunk:
            break
        if pending:
            chunk = pending + chunk

        # Only whole buckets this pass; carry the remainder to the next.
        usable = (len(chunk) // bucket_bytes) * bucket_bytes
        if usable:
            samples = array('f')
            samples.frombytes(chunk[:usable])
            for i in range(0, len(samples), samples_per_bucket):
                window = samples[i:i + samples_per_bucket]
                out.append(min(window))
                out.append(max(window))
        pending = chunk[usable:]

    # Trailing partial bucket, rounded down to whole samples.
    tail = len(pending) // 4 * 4
    if tail:
        samples = array('f')
        samples.frombytes(pending[:tail])
        out.append(min(samples))
        out.append(max(samples))

    return out


def compute_peaks(audio_path, peaks_per_second=PEAKS_PER_SECOND):
    """Decode `audio_path` via ffmpeg and return little-endian Float32 peaks.

    The result is a flat interleaved min/max sequence, which is what
    WaveSurfer's renderer buckets over per pixel.
    """
    samples_per_bucket = max(1, DECODE_SAMPLE_RATE // peaks_per_second)

    cmd = [
        'ffmpeg',
        '-v', 'error',
        '-i', audio_path,
        '-vn',                       # show files carry embedded artwork; without
                                     # this the mjpeg stream corrupts the output
        '-ac', '1',
        '-ar', str(DECODE_SAMPLE_RATE),
        '-f', 'f32le',
        '-',
    ]

    # stderr goes to a real file rather than a pipe we never drain, so a chatty
    # ffmpeg can't fill the buffer and deadlock against our stdout reads.
    with tempfile.TemporaryFile() as errfile:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errfile)
        except FileNotFoundError:
            raise PeaksUnavailable('ffmpeg not found on PATH')

        stdout = proc.stdout
        assert stdout is not None  # guaranteed by stdout=PIPE above
        try:
            peaks = _bucket(stdout, samples_per_bucket)
        finally:
            stdout.close()
            proc.wait()

        if proc.returncode != 0:
            errfile.seek(0)
            detail = errfile.read().decode('utf-8', 'replace').strip()
            raise PeaksUnavailable(
                f'ffmpeg exited {proc.returncode}: {detail or "no output"}')

    if not peaks:
        raise PeaksUnavailable(f'no audio decoded from {audio_path}')

    if sys.byteorder != 'little':
        peaks.byteswap()

    return peaks.tobytes()


# How much to read from each of three positions when fingerprinting a file.
_SAMPLE_BYTES = 1 << 20


def cache_key(audio_path, peaks_per_second=PEAKS_PER_SECOND):
    """Fingerprint a file by size plus sampled contents.

    Deliberately not keyed on path or mtime. Uploads land in a fresh per-process
    tempdir and get a fresh mtime every time, so either would miss on every
    restart and rebuild peaks the user already waited for. Hashing all 278 MB
    would cost about as much as recomputing, so sample head, middle and tail --
    enough that two different shows won't collide.
    """
    size = os.path.getsize(audio_path)

    h = hashlib.sha256()
    for part in (str(size), str(DECODE_SAMPLE_RATE), str(peaks_per_second)):
        h.update(part.encode('utf-8'))
        h.update(b'\0')

    offsets = (0, max(0, size // 2 - _SAMPLE_BYTES // 2), max(0, size - _SAMPLE_BYTES))
    with open(audio_path, 'rb') as f:
        for offset in offsets:
            f.seek(offset)
            h.update(f.read(_SAMPLE_BYTES))

    return h.hexdigest()


def cached_peaks(audio_path, cache_dir, peaks_per_second=PEAKS_PER_SECOND):
    """Return peaks for `audio_path`, computing and caching them on a miss."""
    key = cache_key(audio_path, peaks_per_second)
    cache_file = os.path.join(cache_dir, f'{key}.f32')

    try:
        with open(cache_file, 'rb') as f:
            return f.read()
    except OSError:
        pass

    data = compute_peaks(audio_path, peaks_per_second)

    # Write via a temp file in the same directory so a concurrent reader never
    # sees a half-written cache entry.
    try:
        os.makedirs(cache_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=cache_dir, suffix='.tmp')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            os.replace(tmp_path, cache_file)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        # A broken cache shouldn't break the editor -- just don't cache.
        print(f'Warning: could not cache peaks for {audio_path}: {e}')

    return data


if __name__ == '__main__':
    import time

    if len(sys.argv) < 2:
        print(f'usage: {os.path.basename(sys.argv[0])} <audio-file> [cache-dir]')
        sys.exit(2)

    path = sys.argv[1]
    started = time.perf_counter()

    if len(sys.argv) > 2:
        blob = cached_peaks(path, sys.argv[2])
    else:
        blob = compute_peaks(path)

    elapsed = time.perf_counter() - started
    pairs = len(blob) // 8
    print(f'{len(blob):,} bytes  {pairs:,} min/max pairs  '
          f'{pairs / PEAKS_PER_SECOND:.1f}s of audio  in {elapsed:.2f}s')
