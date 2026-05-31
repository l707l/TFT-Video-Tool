import sys
import os
import subprocess
import shutil

def get_ffmpeg_path():
    """Get the path to ffmpeg executable.
    
    Checks multiple locations:
    1. If running as frozen app (PyInstaller), check _MEIPASS
    2. Check PATH environment variable
    3. Check common Windows install locations
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        ffmpeg_path = os.path.join(base_path, 'bin', 'ffmpeg.exe')
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path
    
    # Check if ffmpeg is in PATH
    ffmpeg_in_path = shutil.which('ffmpeg')
    if ffmpeg_in_path:
        return ffmpeg_in_path
    
    # Check common Windows install locations
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'ffmpeg.exe'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin', 'ffmpeg.exe'),
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    # Return bundled path as fallback
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'ffmpeg.exe')


def find_ffmpeg():
    """Find ffmpeg and return (found: bool, path: str, message: str)"""
    path = get_ffmpeg_path()
    if os.path.exists(path):
        return True, path, f"Found ffmpeg at: {path}"
    
    # Try to find via which/where
    ffmpeg_in_path = shutil.which('ffmpeg')
    if ffmpeg_in_path:
        return True, ffmpeg_in_path, f"Found ffmpeg in PATH: {ffmpeg_in_path}"
    
    return False, "", "FFmpeg not found. Please install FFmpeg or place ffmpeg.exe in the bin/ folder."


def get_ffmpeg_download_url():
    """Return URL for FFmpeg download on Windows"""
    return "https://www.gstatic.com/webp/gallery/3.mp4"


def get_video_info(video_path):
    """Get video information using ffprobe.
    
    Returns dict with:
        - duration: float (seconds)
        - width: int
        - height: int
        - fps: float
        - codec: str
        - audio: bool
        - size_bytes: int
    """
    import json
    
    result = {
        'duration': 0,
        'width': 0,
        'height': 0,
        'fps': 0,
        'codec': '',
        'audio': False,
        'size_bytes': 0
    }
    
    if not os.path.exists(video_path):
        return result
    
    # Get file size
    result['size_bytes'] = os.path.getsize(video_path)
    
    # Try ffprobe
    ffprobe_paths = [
        get_ffmpeg_path().replace('ffmpeg.exe', 'ffprobe.exe'),
        shutil.which('ffprobe'),
        'ffprobe'
    ]
    
    ffprobe = None
    for p in ffprobe_paths:
        if p and os.path.exists(p):
            ffprobe = p
            break
        elif p:
            ffprobe = p
            break
    
    if not ffprobe:
        return result
    
    try:
        cmd = [
            ffprobe,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        output = subprocess.check_output(cmd, timeout=10, stderr=subprocess.DEVNULL)
        data = json.loads(output.decode('utf-8', errors='ignore'))
        
        # Get format info
        fmt = data.get('format', {})
        if fmt:
            result['duration'] = float(fmt.get('duration', 0))
        
        # Get video stream info
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                result['width'] = int(stream.get('width', 0))
                result['height'] = int(stream.get('height', 0))
                result['codec'] = stream.get('codec_name', '')
                
                # Parse FPS
                fps_str = stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    num, den = fps_str.split('/')
                    if int(den) > 0:
                        result['fps'] = int(num) / int(den)
                
            elif stream.get('codec_type') == 'audio':
                result['audio'] = True
                
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, Exception):
        pass
    
    return result


def estimate_output_size(duration_sec, width, height, fps, q, has_audio=True):
    """Estimate output file size in bytes.
    
    Args:
        duration_sec: Video duration in seconds
        width, height: Resolution
        fps: Frames per second
        q: Quality (1-31, lower is better)
        has_audio: Whether audio is included
    
    Returns:
        Estimated size in bytes
    """
    # MJPEG bitrate estimation: higher q = lower bitrate
    # Rough formula: pixels * fps * (32-q) / 8 * compression_factor
    pixels = width * height
    quality_factor = (32 - q) / 10  # 2.1 at q=1, 0.1 at q=31
    
    # MJPEG compression ratio varies but typically 10-30x from raw
    # At q=10, roughly 20x compression
    video_bits_per_second = pixels * fps * quality_factor / 20
    video_bytes_per_second = video_bits_per_second / 8
    
    # Audio: MP3 at 44100 Hz typically ~128kbps = 16KB/s
    audio_bytes_per_second = 16000 if has_audio else 0
    
    total_bytes_per_second = video_bytes_per_second + audio_bytes_per_second
    estimated = total_bytes_per_second * duration_sec
    
    # Add header overhead (~1%)
    estimated *= 1.01
    
    return max(estimated, 0)


def format_bytes(size_bytes):
    """Format bytes as human readable string"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    else:
        return f"{size_bytes / (1024*1024*1024):.2f} GB"


def is_windows():
    """Check if running on Windows"""
    return sys.platform.startswith('win')


def ensure_ffmpeg_available():
    """Check if ffmpeg is available and provide guidance if not"""
    found, path, msg = find_ffmpeg()
    if found:
        return True, path
    
    # Windows-specific guidance
    if is_windows():
        msg = (
            "FFmpeg not found. Please:\n\n"
            "1. Download FFmpeg from: https://www.gyan.dev/ffmpeg/builds/\n"
            "2. Extract to a folder (e.g., C:\\ffmpeg)\n"
            "3. Add to PATH, or place ffmpeg.exe in the bin/ folder\n\n"
            "Quick install with Chocolatey:\n"
            "   choco install ffmpeg\n"
        )
    else:
        msg = (
            "FFmpeg not found. Please install FFmpeg:\n\n"
            "   Ubuntu/Debian: sudo apt install ffmpeg\n"
            "   macOS: brew install ffmpeg\n"
            "   Or: sudo apt install ffmpeg\n"
        )
    
    return False, msg