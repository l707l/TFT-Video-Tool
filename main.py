import sys
import os
import shlex
import argparse
import qtawesome as qta
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLineEdit, QPushButton, 
                               QFileDialog, QComboBox, QSlider, QFrame, 
                               QTextEdit, QGridLayout, QSizePolicy,
                               QMessageBox, QLabel, QDialog, QProgressBar,
                               QCheckBox, QGroupBox, QStatusBar)
from PySide6.QtCore import Qt, QUrl, QTimer, QSize, QProcess, QSettings, QThread, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtGui import QTextCursor

from widgets import ClickableSlider, FixedAspectRatioWidget
from styles import get_stylesheet
from utils import (get_ffmpeg_path, find_ffmpeg, get_video_info, 
                   estimate_output_size, format_bytes, ensure_ffmpeg_available)


class BatchWorker(QThread):
    """Worker thread for batch conversion"""
    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(int, int)  # success_count, total_count
    error = Signal(str)
    
    def __init__(self, file_list, output_dir, settings):
        super().__init__()
        self.file_list = file_list
        self.output_dir = output_dir
        self.settings = settings
        self.running = True
    
    def stop(self):
        self.running = False
    
    def run(self):
        success_count = 0
        total = len(self.file_list)
        
        for i, input_path in enumerate(self.file_list):
            if not self.running:
                break
            
            try:
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                suffix = self.settings.get('suffix', '_mjpeg.avi')
                output_path = os.path.join(self.output_dir, f"{base_name}{suffix}")
                
                self.progress.emit(i + 1, total, os.path.basename(input_path))
                
                cmd = self.build_command(input_path, output_path)
                if cmd:
                    result = self.run_ffmpeg(cmd)
                    if result == 0:
                        success_count += 1
                    elif result is None:
                        break  # Cancelled
                else:
                    self.error.emit(f"Failed to build command for {input_path}")
                    
            except Exception as e:
                self.error.emit(f"Error processing {input_path}: {str(e)}")
        
        self.finished.emit(success_count, total)
    
    def build_command(self, input_path, output_path):
        """Build FFmpeg command for batch processing"""
        w = self.settings.get('width', '240')
        h = self.settings.get('height', '320')
        fps = self.settings.get('fps', '30')
        q = self.settings.get('q', '10')
        ar = self.settings.get('ar', '44100')
        vcodec = self.settings.get('vcodec', 'mjpeg')
        acodec = self.settings.get('acodec', 'mp3')
        aspect_mode = self.settings.get('aspect_mode', 'Fit')
        
        ffmpeg_exe = get_ffmpeg_path()
        if not os.path.exists(ffmpeg_exe):
            return None
        
        ac_cmd = "mp3" if acodec == "mp3" else "pcm_u8"
        
        out_w = int(w)
        out_h = int(h)
        if vcodec == "cinepak":
            if out_w % 4 != 0: out_w = int(round(out_w / 4) * 4)
            if out_h % 4 != 0: out_h = int(round(out_h / 4) * 4)
        
        inp = f'"{input_path}"'
        out = f'"{output_path}"'
        
        vf_parts = [f"fps={fps}"]
        
        if aspect_mode == "Stretch":
            vf_parts.append(f"scale={out_w}:{out_h}:flags=lanczos")
        elif aspect_mode == "Fit":
            vf_parts.append(f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:flags=lanczos")
            vf_parts.append(f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2")
        elif aspect_mode == "Cover":
            vf_parts.append(f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase:flags=lanczos")
            vf_parts.append(f"crop={out_w}:{out_h}")
        
        vf = ",".join(vf_parts)
        
        cmd = (f'"{ffmpeg_exe}" -y -i {inp} -ac 2 -ar {ar} -af loudnorm '
               f'-c:a {ac_cmd} -c:v {vcodec} -q:v {q} -vf "{vf}" {out}')
        
        return cmd
    
    def run_ffmpeg(self, cmd):
        """Run FFmpeg command and return exit code, None if cancelled"""
        args = shlex.split(cmd)
        process = QProcess()
        process.start(args[0], args[1:])
        process.waitForFinished(-1)
        return process.exitCode()


class AboutDialog(QDialog):
    """About ESP32-2432S028 Dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About ESP32-2432S028")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("ESP32-2432S028")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f1c40f;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("\"Cheap Yellow Display\" (CYD)")
        subtitle.setStyleSheet("font-size: 14px; color: #e0e0e0;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(10)
        
        # Description
        desc = QLabel(
            "A budget ESP32 development board with built-in 2.8\" TFT display.\n"
            "Perfect for video playback projects on embedded systems."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)
        
        layout.addSpacing(10)
        
        # Specifications
        specs_group = QGroupBox("Specifications")
        specs_layout = QVBoxLayout(specs_group)
        
        specs = [
            "• Display: 2.8\" ILI9341 TFT LCD",
            "• Resolution: 240x320 pixels",
            "• Interface: SPI",
            "• Chip: ESP32 (dual-core, 240MHz)",
            "• Storage: MicroSD card slot",
            "• Camera: Optional OV2640 interface",
            "• USB: USB-C for power/programming",
        ]
        
        for spec in specs:
            label = QLabel(spec)
            specs_layout.addWidget(label)
        
        layout.addWidget(specs_group)
        
        # Pinout
        pinout_group = QGroupBox("TFT Pinout (for video playback)")
        pinout_layout = QVBoxLayout(pinout_group)
        
        pinout = [
            "• TFT_CS   → GPIO 15",
            "• TFT_RST  → GPIO 4",
            "• TFT_DC   → GPIO 2",
            "• TFT_MOSI → GPIO 23 (SDA)",
            "• TFT_SCLK → GPIO 18 (SCK)",
            "• TFT_MISO → GPIO 19",
            "• SD_CS    → GPIO 13",
            "• BL (Backlight) → GPIO 21",
        ]
        
        for pin in pinout:
            label = QLabel(pin)
            pinout_layout.addWidget(label)
        
        layout.addWidget(pinout_group)
        
        # ESP32 Sketch Info
        sketch_group = QGroupBox("Arduino/ESP32 Sketch Requirements")
        sketch_layout = QVBoxLayout(sketch_group)
        
        sketch_info = [
            "1. Install TFT_eSPI library",
            "2. Configure User_Setup.h for ILI9341",
            "3. Use SPI speed 40-80MHz for video",
            "4. Buffering: Use frame buffer or DMA",
            "5. SD card must be formatted as FAT32",
        ]
        
        for info in sketch_info:
            label = QLabel(info)
            sketch_layout.addWidget(label)
        
        layout.addWidget(sketch_group)
        
        # Close button
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(40)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class BatchDialog(QDialog):
    """Batch conversion dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Conversion")
        self.file_list = []
        self.output_dir = ""
        self.settings = {}
        self.worker = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Input folder selection
        input_layout = QHBoxLayout()
        self.txt_input_folder = QLineEdit()
        self.txt_input_folder.setPlaceholderText("Select folder with videos...")
        self.txt_input_folder.setReadOnly(True)
        btn_browse_input = QPushButton("Browse...")
        btn_browse_input.clicked.connect(self.browse_input_folder)
        input_layout.addWidget(QLabel("Input Folder:"))
        input_layout.addWidget(self.txt_input_folder)
        input_layout.addWidget(btn_browse_input)
        layout.addLayout(input_layout)
        
        # Output folder selection
        output_layout = QHBoxLayout()
        self.txt_output_folder = QLineEdit()
        self.txt_output_folder.setPlaceholderText("Select output folder...")
        self.txt_output_folder.setReadOnly(True)
        btn_browse_output = QPushButton("Browse...")
        btn_browse_output.clicked.connect(self.browse_output_folder)
        output_layout.addWidget(QLabel("Output Folder:"))
        output_layout.addWidget(self.txt_output_folder)
        output_layout.addWidget(btn_browse_output)
        layout.addLayout(output_layout)
        
        # File list
        self.lbl_file_count = QLabel("No files selected")
        layout.addWidget(self.lbl_file_count)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.lbl_progress = QLabel("")
        layout.addWidget(self.lbl_progress)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Start Conversion")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.start_conversion)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_conversion)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
    
    def browse_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.txt_input_folder.setText(folder)
            self.scan_folder(folder)
    
    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.txt_output_folder.setText(folder)
    
    def scan_folder(self, folder):
        """Scan folder for video files"""
        video_exts = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        self.file_list = []
        
        for f in os.listdir(folder):
            ext = os.path.splitext(f)[1].lower()
            if ext in video_exts:
                self.file_list.append(os.path.join(folder, f))
        
        count = len(self.file_list)
        self.lbl_file_count.setText(f"{count} video file(s) found")
        self.btn_start.setEnabled(count > 0 and bool(self.txt_output_folder.text()))
    
    def set_settings(self, settings):
        self.settings = settings
    
    def start_conversion(self):
        if not self.file_list or not self.output_dir:
            return
        
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.file_list))
        self.progress_bar.setValue(0)
        
        self.worker = BatchWorker(self.file_list, self.output_dir, self.settings)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def cancel_conversion(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
    
    def on_progress(self, current, total, filename):
        self.progress_bar.setValue(current)
        self.lbl_progress.setText(f"Converting: {filename} ({current}/{total})")
    
    def on_finished(self, success, total):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_progress.setText(f"Completed: {success}/{total} files converted successfully")
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "Batch Conversion Complete", 
                               f"Successfully converted {success} of {total} files.")
    
    def on_error(self, error_msg):
        self.lbl_progress.setText(f"Error: {error_msg}")


class VideoProcessorApp(QMainWindow):
    def __init__(self, cli_args=None):
        super().__init__()
        self.cli_args = cli_args
        self.setWindowTitle("TFT Video Tool")
        self.resize(1000, 750)
        self.center_window()
        
        self.settings = QSettings("MyCompany", "FFmpegTool")
        self.is_dark_mode = False
        self.input_path = ""
        self.duration = 0
        self.updating_from_code = False
        self.process = None
        self.was_playing_before_seek = False
        self.batch_dialog = None
        
        self.setup_ui()
        self.load_settings()
        self.apply_theme()
        self.apply_preset()
        self.init_process()
        
        # Check for FFmpeg
        found, path_or_msg = ensure_ffmpeg_available()
        if not found:
            QMessageBox.warning(self, "FFmpeg Not Found", path_or_msg)
        
        # CLI mode
        if cli_args and cli_args.get('input'):
            QTimer.singleShot(100, self.handle_cli_mode)
    
    def handle_cli_mode(self):
        """Handle CLI mode conversion"""
        args = self.cli_args
        input_video = args.get('input')
        output_video = args.get('output')
        
        if not os.path.exists(input_video):
            print(f"Error: Input file not found: {input_video}")
            sys.exit(1)
        
        # Set parameters from CLI
        if args.get('width'):
            self.txt_width.setText(str(args['width']))
        if args.get('height'):
            self.txt_height.setText(str(args['height']))
        if args.get('fps'):
            self.txt_fps.setText(str(args['fps']))
        
        # Load video to get info
        self.input_path = input_video
        self.lbl_file_path.setText(os.path.basename(input_video))
        self.media_player.setSource(QUrl.fromLocalFile(input_video))
        
        # Update settings from CLI preset if specified
        if args.get('preset'):
            preset_idx = self.combo_presets.findText(args['preset'])
            if preset_idx >= 0:
                self.combo_presets.setCurrentIndex(preset_idx)
        
        # Run conversion
        cmd = self.get_command_string(specific_output_path=output_video)
        if not cmd:
            print("Error: Invalid conversion parameters")
            sys.exit(1)
        
        print(f"Running: {cmd}")
        
        # Execute directly
        import subprocess
        result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Success! Output saved to: {output_video}")
        else:
            print(f"Error: {result.stderr}")
            sys.exit(1)
        
        sys.exit(0)
    
    def center_window(self):
        frame_geo = self.frameGeometry()
        screen = self.screen().availableGeometry().center()
        frame_geo.moveCenter(screen)
        self.move(frame_geo.topLeft())

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self.update_logic)

    def closeEvent(self, event):
        self.save_settings()
        if self.batch_dialog:
            self.batch_dialog.close()
        super().closeEvent(event)

    def init_process(self):
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        
        self.btn_open = QPushButton("📂")
        self.btn_open.setObjectName("btn_open")
        self.btn_open.setFixedSize(40, 40)
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self.open_file)
        
        self.btn_batch = QPushButton("📁")
        self.btn_batch.setObjectName("btn_batch")
        self.btn_batch.setFixedSize(40, 40)
        self.btn_batch.setCursor(Qt.PointingHandCursor)
        self.btn_batch.clicked.connect(self.open_batch_dialog)
        self.btn_batch.setToolTip("Batch Conversion")
        
        self.lbl_file_path = QLineEdit()
        self.lbl_file_path.setPlaceholderText("No video selected...")
        self.lbl_file_path.setReadOnly(True)
        self.lbl_file_path.setFixedHeight(40)
        
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setFixedSize(40, 40)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)

        header_layout.addWidget(self.btn_open)
        header_layout.addWidget(self.btn_batch)
        header_layout.addWidget(self.lbl_file_path)
        header_layout.addWidget(self.btn_theme)
        main_layout.addLayout(header_layout)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        self.aspect_ratio_box = FixedAspectRatioWidget()
        self.video_widget = QVideoWidget()
        self.aspect_ratio_box.set_child_widget(self.video_widget)
        
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.playbackStateChanged.connect(self.media_state_changed)

        self.preview_spacer = QWidget()
        self.preview_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        preview_layout.addWidget(self.aspect_ratio_box, 1)
        preview_layout.addWidget(self.preview_spacer, 1)

        bottom_controls = QWidget()
        bottom_layout = QVBoxLayout(bottom_controls)
        bottom_layout.setContentsMargins(0, 10, 0, 0)
        bottom_layout.setSpacing(5)

        ctrl_layout = QHBoxLayout()
        
        self.btn_play = QPushButton()
        self.btn_play.setObjectName("btn_play")
        self.btn_play.setFixedSize(40, 30)
        self.btn_play.setFlat(True) 
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self.toggle_play)
        
        self.slider_seek = ClickableSlider(Qt.Horizontal)
        self.slider_seek.setFixedHeight(20)
        self.slider_seek.setCursor(Qt.PointingHandCursor)
        self.slider_seek.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.slider_seek.sliderPressed.connect(self.on_slider_pressed)
        self.slider_seek.sliderMoved.connect(self.set_position)
        self.slider_seek.sliderReleased.connect(self.on_slider_released)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setAlignment(Qt.AlignCenter)
        self.lbl_time.setFixedWidth(100)

        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.slider_seek)
        ctrl_layout.addWidget(self.lbl_time)

        self.combo_aspect = QComboBox()
        self.combo_aspect.addItems(["Fit", "Cover", "Stretch"])
        self.combo_aspect.currentIndexChanged.connect(self.change_aspect_ratio_mode)
        self.combo_aspect.currentIndexChanged.connect(self.update_logic)

        bottom_layout.addLayout(ctrl_layout)
        bottom_layout.addWidget(self.combo_aspect)
        preview_layout.addWidget(bottom_controls)

        settings_container = QWidget()
        settings_layout = QVBoxLayout(settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        
        grid = QGridLayout()
        grid.setVerticalSpacing(15)
        grid.setHorizontalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        
        # Presets with CYD as first
        self.combo_presets = QComboBox()
        base_config = {"fps": "30", "q": "10", "vcodec": "mjpeg", "acodec": "mp3", "ar": "44100", "suffix": ".mjpeg"}
        def make_data(w, h):
            d = base_config.copy(); d.update({"w": w, "h": h}); return d

        # CYD (Cheap Yellow Display) - ESP32-2432S028 as FIRST preset
        # Extension .mjpeg (NOT .avi) - folder /mjpeg on SD card
        cyd_config = {"fps": "30", "q": "10", "vcodec": "mjpeg", "acodec": "mp3", "ar": "44100", "suffix": ".mjpeg", "w": "240", "h": "320"}
        self.combo_presets.addItem("CYD (ESP32-2432S028) 240x320", cyd_config)
        self.combo_presets.addItem("CYD (thelastoutpost) 240x320", cyd_config.copy())
        self.combo_presets.addItem("Landscape (320x170)", make_data("320", "170"))
        self.combo_presets.addItem("Landscape (280x240)", make_data("280", "240"))
        self.combo_presets.addItem("Portrait (170x320)", make_data("170", "320"))
        self.combo_presets.addItem("Portrait (240x280)", make_data("240", "280"))
        self.combo_presets.addItem("Custom", "custom")
        self.combo_presets.currentIndexChanged.connect(self.apply_preset)

        # About CYD button
        self.btn_about_cyd = QPushButton("ℹ️ CYD Info")
        self.btn_about_cyd.setCursor(Qt.PointingHandCursor)
        self.btn_about_cyd.clicked.connect(self.show_about_cyd)

        self.combo_strategy = QComboBox()
        self.combo_strategy.addItem("Portrait", "portrait")
        self.combo_strategy.addItem("Landscape", "landscape")
        self.combo_strategy.activated.connect(self.swap_dimensions)

        grid.addWidget(self.combo_presets, 0, 0)
        grid.addWidget(self.btn_about_cyd, 0, 1)
        grid.addWidget(self.combo_strategy, 1, 0, 1, 2)

        self.txt_width = QLineEdit()
        self.txt_width.setPlaceholderText("W")
        self.txt_width.setAlignment(Qt.AlignCenter)
        self.lbl_x = QLabel("x")
        self.lbl_x.setAlignment(Qt.AlignCenter)
        self.lbl_x.setFixedWidth(15)
        self.txt_height = QLineEdit()
        self.txt_height.setPlaceholderText("H")
        self.txt_height.setAlignment(Qt.AlignCenter)

        size_layout = QHBoxLayout()
        size_layout.addWidget(self.txt_width, 1) 
        size_layout.addWidget(self.lbl_x, 0)
        size_layout.addWidget(self.txt_height, 1)
        grid.addLayout(size_layout, 2, 0, 1, 2)

        self.txt_fps = QLineEdit(); self.txt_fps.setPlaceholderText("FPS")
        self.txt_qscale = QLineEdit(); self.txt_qscale.setPlaceholderText("Q (1-31)")
        grid.addWidget(self.txt_fps, 3, 0)
        grid.addWidget(self.txt_qscale, 3, 1)

        self.combo_vcodec = QComboBox(); self.combo_vcodec.addItems(["mjpeg", "cinepak"])
        self.combo_vcodec.currentIndexChanged.connect(self.sync_suffix_with_codec)
        self.combo_acodec = QComboBox(); self.combo_acodec.addItems(["mp3", "pcm"])
        grid.addWidget(self.combo_vcodec, 4, 0)
        grid.addWidget(self.combo_acodec, 4, 1)

        self.txt_ar = QLineEdit(); self.txt_ar.setPlaceholderText("Hz")
        self.txt_suffix = QLineEdit(); self.txt_suffix.setPlaceholderText("Ext")
        grid.addWidget(self.txt_ar, 5, 0)
        grid.addWidget(self.txt_suffix, 5, 1)

        settings_layout.addLayout(grid)
        
        self.txt_output_name = QLineEdit()
        self.txt_output_name.setPlaceholderText("Output Filename (Optional)")
        self.txt_output_name.textChanged.connect(self.update_logic)
        settings_layout.addWidget(self.txt_output_name)
        
        # Estimated size label
        self.lbl_estimated_size = QLabel("")
        self.lbl_estimated_size.setStyleSheet("color: #3498db; font-weight: bold;")
        settings_layout.addWidget(self.lbl_estimated_size)
        
        self.txt_command = QTextEdit()
        self.txt_command.setReadOnly(True)
        self.txt_command.setPlaceholderText("FFmpeg command...")
        self.txt_command.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        settings_layout.addWidget(self.txt_command)

        self.btn_export = QPushButton("EXPORT")
        self.btn_export.setFixedHeight(50)
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.clicked.connect(self.run_ffmpeg)
        settings_layout.addWidget(self.btn_export)

        content_layout.addWidget(preview_container, 6)
        content_layout.addWidget(settings_container, 4)
        
        main_layout.addLayout(content_layout)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFixedHeight(120)
        self.txt_log.setFrameShape(QFrame.NoFrame)
        self.txt_log.setObjectName("console_log")
        main_layout.addWidget(self.txt_log)

        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        
        widgets_to_validate = [self.txt_width, self.txt_height, self.txt_fps, self.txt_qscale, self.txt_ar, self.txt_suffix]
        for w in widgets_to_validate: w.textChanged.connect(self.validate_inputs)
        
        widgets = [self.txt_width, self.txt_height, self.txt_fps, self.txt_qscale, self.txt_ar, self.txt_suffix, self.combo_strategy, self.combo_vcodec, self.combo_acodec]
        for w in widgets:
            if isinstance(w, QLineEdit): w.textChanged.connect(self.update_logic)
            elif isinstance(w, QComboBox): w.currentIndexChanged.connect(self.update_logic)
        
        self.validate_inputs() 
        self.update_logic()

    def show_about_cyd(self):
        """Show About ESP32-2432S028 dialog"""
        dialog = AboutDialog(self)
        dialog.exec()

    def open_batch_dialog(self):
        """Open batch conversion dialog"""
        if self.batch_dialog is None:
            self.batch_dialog = BatchDialog(self)
        
        # Pass current settings
        settings = {
            'width': self.txt_width.text(),
            'height': self.txt_height.text(),
            'fps': self.txt_fps.text(),
            'q': self.txt_qscale.text(),
            'ar': self.txt_ar.text(),
            'vcodec': self.combo_vcodec.currentText(),
            'acodec': self.combo_acodec.currentText(),
            'aspect_mode': self.combo_aspect.currentText(),
            'suffix': self.txt_suffix.text(),
        }
        self.batch_dialog.set_settings(settings)
        self.batch_dialog.show()

    def validate_inputs(self):
        fields = [self.txt_width, self.txt_height, self.txt_fps, self.txt_qscale, self.txt_ar, self.txt_suffix]
        is_valid = True
        for field in fields:
            if not field.text().strip():
                is_valid = False
                field.setProperty("error", True)
            else:
                field.setProperty("error", False)
            field.style().unpolish(field)
            field.style().polish(field)

        if self.process and self.process.state() == QProcess.Running:
             self.btn_export.setEnabled(False)
        else:
            self.btn_export.setEnabled(is_valid)

    def sync_suffix_with_codec(self):
        vcodec = self.combo_vcodec.currentText()
        if vcodec == "mjpeg": self.txt_suffix.setText(".mjpeg")
        elif vcodec == "cinepak": self.txt_suffix.setText(".avi")

    def apply_preset(self):
        if self.updating_from_code: return
        data = self.combo_presets.currentData()
        self.updating_from_code = True 
        if isinstance(data, dict):
            w = data.get("w", ""); h = data.get("h", "")
            self.txt_width.setText(w); self.txt_height.setText(h)
            self.txt_fps.setText(data.get("fps", ""))
            self.txt_qscale.setText(data.get("q", ""))
            self.txt_ar.setText(data.get("ar", ""))
            self.txt_suffix.setText(data.get("suffix", ""))
            idx_v = self.combo_vcodec.findText(data.get("vcodec", "")); 
            if idx_v != -1: self.combo_vcodec.setCurrentIndex(idx_v)
            idx_a = self.combo_acodec.findText(data.get("acodec", "")); 
            if idx_a != -1: self.combo_acodec.setCurrentIndex(idx_a)
            try:
                if int(w) >= int(h):
                    idx = self.combo_strategy.findData("landscape")
                    if idx != -1: self.combo_strategy.setCurrentIndex(idx)
                else:
                    idx = self.combo_strategy.findData("portrait")
                    if idx != -1: self.combo_strategy.setCurrentIndex(idx)
            except ValueError: pass
        elif data == "custom":
            self.txt_width.setText(""); self.txt_height.setText("")
            self.txt_fps.setText(""); self.txt_qscale.setText("")
            self.txt_ar.setText(""); self.txt_suffix.setText("")
        self.updating_from_code = False
        self.validate_inputs()
        self.update_logic()

    def sync_preset_from_text(self):
        if self.updating_from_code: return
        w = self.txt_width.text(); h = self.txt_height.text()
        self.updating_from_code = True
        current_data = self.combo_presets.currentData()
        match = False
        if isinstance(current_data, dict):
            if current_data.get("w") == w and current_data.get("h") == h: match = True
        if not match:
            custom_idx = self.combo_presets.findData("custom")
            if custom_idx != -1: self.combo_presets.setCurrentIndex(custom_idx)
        self.updating_from_code = False

    def load_settings(self):
        val = self.settings.value("is_dark_mode", False)
        self.is_dark_mode = (str(val).lower() == 'true')
    
    def save_settings(self):
        self.settings.setValue("is_dark_mode", self.is_dark_mode)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.update_play_button_icon("pause")
        else:
            self.update_play_button_icon("play")

    def update_play_button_icon(self, state):
        icon_color = "#ffffff" if self.is_dark_mode else "#000000"
        if state == "play": icon = qta.icon('fa5s.play', color=icon_color)
        else: icon = qta.icon('fa5s.pause', color=icon_color)
        self.btn_play.setIcon(icon)
        self.btn_play.setIconSize(QSize(20, 20))

    def media_state_changed(self, state):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.update_play_button_icon("pause")
        else:
            self.update_play_button_icon("play")

    def apply_theme(self):
        sheet, icon_col = get_stylesheet(self.is_dark_mode)
        self.setStyleSheet(sheet)
        if self.is_dark_mode: self.btn_theme.setIcon(qta.icon('fa5s.moon', color=icon_col))
        else: self.btn_theme.setIcon(qta.icon('fa5s.sun', color=icon_col))
        self.btn_theme.setIconSize(QSize(20, 20))
        if self.media_player.playbackState() == QMediaPlayer.PlayingState: self.update_play_button_icon("pause")
        else: self.update_play_button_icon("play")

    def swap_dimensions(self):
        w = self.txt_width.text(); h = self.txt_height.text()
        self.txt_width.blockSignals(True); self.txt_height.blockSignals(True)
        self.txt_width.setText(h); self.txt_height.setText(w)
        self.txt_width.blockSignals(False); self.txt_height.blockSignals(False)
        self.sync_preset_from_text()
        self.update_logic()

    def update_logic(self):
        has_dims = self.aspect_ratio_box.set_target_ratio(self.txt_width.text(), self.txt_height.text())
        if has_dims: self.preview_spacer.hide()
        else: self.preview_spacer.show()
        self.update_command()
        self.update_estimated_size()

    def update_estimated_size(self):
        """Update the estimated file size display"""
        if not self.input_path:
            self.lbl_estimated_size.setText("")
            return
        
        try:
            w = int(self.txt_width.text())
            h = int(self.txt_height.text())
            fps = int(self.txt_fps.text())
            q = int(self.txt_qscale.text())
            ar = int(self.txt_ar.text())
            duration = self.media_player.duration() / 1000  # ms to seconds
            
            has_audio = self.combo_acodec.currentText() != "pcm"
            
            if duration > 0:
                estimated = estimate_output_size(duration, w, h, fps, q, has_audio)
                size_str = format_bytes(estimated)
                self.lbl_estimated_size.setText(f"Estimated output size: ~{size_str}")
            else:
                self.lbl_estimated_size.setText("")
        except (ValueError, ZeroDivisionError):
            self.lbl_estimated_size.setText("")

    def change_aspect_ratio_mode(self, index):
        modes = [Qt.KeepAspectRatio, Qt.KeepAspectRatioByExpanding, Qt.IgnoreAspectRatio]
        self.video_widget.setAspectRatioMode(modes[index])
        s = self.video_widget.size()
        self.video_widget.resize(s.width(), s.height()-1)
        self.video_widget.resize(s)

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm)")
        if file_name:
            self.input_path = file_name
            self.lbl_file_path.setText(os.path.basename(file_name))
            self.media_player.setSource(QUrl.fromLocalFile(file_name))
            self.media_player.play()
            self.validate_inputs()
            self.update_logic()

    def toggle_play(self):
        if not self.input_path: return 
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
    
    def play_video(self): 
        self.media_player.play()
    
    def pause_video(self): 
        self.media_player.pause()
    
    def on_slider_pressed(self):
        if not self.input_path: return
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.was_playing_before_seek = True; self.media_player.pause()
        else: self.was_playing_before_seek = False

    def on_slider_released(self):
        if not self.input_path: return
        if self.was_playing_before_seek:
            self.media_player.play()
        else:
            self.media_player.pause()
            
    def set_position(self, pos): self.media_player.setPosition(pos)
    
    def format_time(self, ms):
        seconds = (ms // 1000) % 60
        minutes = (ms // 60000)
        return f"{minutes:02}:{seconds:02}"

    def update_time_label(self):
        current = self.media_player.position()
        total = self.media_player.duration()
        self.lbl_time.setText(f"{self.format_time(current)} / {self.format_time(total)}")

    def position_changed(self, pos): 
        if not self.slider_seek.isSliderDown(): self.slider_seek.setValue(pos)
        self.update_time_label()

    def duration_changed(self, dur): 
        self.duration = dur; self.slider_seek.setRange(0, dur)
        self.update_time_label()
        self.update_estimated_size()

    def get_command_string(self, specific_output_path=None):
        if not self.input_path: return ""
        
        w_str = self.txt_width.text()
        h_str = self.txt_height.text()
        fps = self.txt_fps.text()
        q = self.txt_qscale.text()
        ar = self.txt_ar.text()
        suffix = self.txt_suffix.text()
        
        if not (w_str and h_str and fps and q and ar and suffix): return ""
        try: 
            w_int = int(w_str)
            h_int = int(h_str)
        except ValueError: return ""

        vcodec = self.combo_vcodec.currentText()
        acodec = self.combo_acodec.currentText()
        ac_cmd = "mp3" if acodec == "mp3" else "pcm_u8"
        aspect_mode = self.combo_aspect.currentText()
        out_w = w_int
        out_h = h_int

        if vcodec == "cinepak":
            if out_w % 4 != 0: out_w = int(round(out_w / 4) * 4)
            if out_h % 4 != 0: out_h = int(round(out_h / 4) * 4)

        inp = f'"{self.input_path}"'
        
        if specific_output_path:
            out = f'"{specific_output_path}"'
        else:
            output_name = self.txt_output_name.text().strip()
            out_base = output_name if output_name else os.path.splitext(os.path.basename(self.input_path))[0]
            out = f'"{out_base}{suffix}"'

        ffmpeg_exe = get_ffmpeg_path()
        vf_parts = [f"fps={fps}"]
        
        if aspect_mode == "Stretch":
            vf_parts.append(f"scale={out_w}:{out_h}:flags=lanczos")
        elif aspect_mode == "Fit":
            vf_parts.append(f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:flags=lanczos")
            vf_parts.append(f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2")
        elif aspect_mode == "Cover":
            vf_parts.append(f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase:flags=lanczos")
            vf_parts.append(f"crop={out_w}:{out_h}")
        vf = ",".join(vf_parts)

        cmd = (f'"{ffmpeg_exe}" -y -i {inp} -ac 2 -ar {ar} -af loudnorm '
               f'-c:a {ac_cmd} -c:v {vcodec} -q:v {q} -vf "{vf}" {out}')
        return cmd

    def update_command(self):
        cmd = self.get_command_string(specific_output_path=None)
        self.txt_command.setText(cmd)

    def run_ffmpeg(self):
        if not self.btn_export.isEnabled() or not self.input_path: return
        ffmpeg_exe = get_ffmpeg_path()
        if not os.path.exists(ffmpeg_exe):
            QMessageBox.critical(self, "Error", f"FFmpeg not found at:\n{ffmpeg_exe}")
            return
        if self.process.state() == QProcess.Running: return

        suffix = self.txt_suffix.text()
        user_name = self.txt_output_name.text().strip()
        
        if user_name:
            if not user_name.endswith(suffix): user_name += suffix
            suggestion = user_name
        else:
            base_name = os.path.splitext(os.path.basename(self.input_path))[0]
            suggestion = f"{base_name}{suffix}"

        initial_path = os.path.join(os.path.dirname(self.input_path), suggestion)

        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Video As", 
            initial_path, 
            "Video Files (*.avi *.mp4 *.mkv)"
        )

        if not file_path:
            self.txt_log.append(">>> Export cancelled by user.")
            return

        self.txt_log.clear()
        self.txt_log.append(f">>> Saving to: {file_path}")
        self.txt_log.append(f">>> Estimated size: {self.lbl_estimated_size.text().replace('Estimated output size: ', '')}")
        self.txt_log.append(">>> Starting FFmpeg...")
        
        cmd_str = self.get_command_string(specific_output_path=file_path)
        self.txt_command.setText(cmd_str) 

        args = shlex.split(cmd_str)
        self.btn_export.setEnabled(False)
        self.btn_export.setText("RUNNING...")
        self.process.start(args[0], args[1:])

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        self.append_log(data.data().decode('utf-8', errors='ignore'))
    def handle_stderr(self):
        data = self.process.readAllStandardError()
        self.append_log(data.data().decode('utf-8', errors='ignore'))
    def append_log(self, text):
        self.txt_log.moveCursor(QTextCursor.End); self.txt_log.insertPlainText(text); self.txt_log.moveCursor(QTextCursor.End)
    def process_finished(self):
        self.btn_export.setEnabled(True); self.btn_export.setText("EXPORT")
        self.append_log("\n>>> FFmpeg Finished.")


def parse_cli_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='TFT Video Tool - Convert videos for embedded TFT displays')
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode (no GUI)')
    parser.add_argument('--input', '-i', type=str, help='Input video file')
    parser.add_argument('--output', '-o', type=str, help='Output video file')
    parser.add_argument('--width', '-w', type=int, help='Output width')
    parser.add_argument('--height', type=int, help='Output height')
    parser.add_argument('--fps', type=int, default=30, help='Frames per second (default: 30)')
    parser.add_argument('--quality', '-q', type=int, default=10, help='Quality 1-31 (default: 10)')
    parser.add_argument('--preset', type=str, help='Preset name')
    
    args = parser.parse_args()
    
    if args.cli:
        if not args.input or not args.output:
            parser.error('--cli mode requires --input and --output')
    
    return args


if __name__ == "__main__":
    cli_args = parse_cli_args()
    
    if cli_args.cli:
        # Pure CLI mode
        app = QApplication(sys.argv)
        window = VideoProcessorApp(vars(cli_args))
    else:
        app = QApplication(sys.argv)
        window = VideoProcessorApp()
        window.show()
    
    sys.exit(app.exec())