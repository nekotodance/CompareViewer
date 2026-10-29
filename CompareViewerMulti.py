import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QStatusBar, QHBoxLayout
from PyQt5.QtGui import QPixmap, QCursor, QIcon, QMovie, QImageReader
from PyQt5.QtCore import Qt, QPoint, QSize, QTimer
from PyQt5.QtMultimedia import QSound
import pvsubfunc
from natsort import os_sorted

# アプリ名称
WINDOW_TITLE = "Compare Viewer Multi 0.1.1"
# 設定ファイル
SETTINGS_FILE = "CompareViewerMulti_settings.json"
# 設定ファイルのキー名
SOUND_MOVE_TOP = "sound-move-top"
SOUND_MOVE_END = "sound-move-end"
GEOMETRY_X = "geometry-x"
GEOMETRY_Y = "geometry-y"
GEOMETRY_W = "geometry-w"
GEOMETRY_H = "geometry-h"
AUTO_INTERVAL = "auto-interval"
VISIBLE_COUNT = "visible-count"

SUPPORT_EXT = [".png", ".jpg", ".jpeg", ".webp"]
MAX_VIEW = 6

# 背景カラーをスロットごとに変更
BACK_COLORS = [
    "background-color: #222222;",
    "background-color: #161616;",
    "background-color: #1c1c1c;",
    "background-color: #0d0d0d;",
    "background-color: #111111;",
    "background-color: #080808;"
]

class CompareViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.visible_count = MAX_VIEW
        self.auto_interval = 4

        # 押下中のキーの順序を保持するリスト（押し順ケア用）
        self.active_swap_keys = []

        # 自動ページ送り用タイマー
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(lambda: self.navigate_images(1))

        self.init_ui()

    def init_ui(self):
        self.image_paths = [None] * MAX_VIEW
        self.image_dirs = [None] * MAX_VIEW
        self.image_sizestr = [""] * MAX_VIEW
        self.imagefiles_digits = 1
        self.current_indices = [0] * MAX_VIEW
        self.soundMoveTop = ""
        self.soundMoveEnd = ""
        self.pydir = os.path.dirname(os.path.abspath(__file__))
        self.dragging = False
        self.last_pos = None
        self.fitscreen = -1
        self.fullscreen = False

        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(0, 0, 1200, 600)
        self.setMinimumSize(400, 320)

        if not os.path.exists(SETTINGS_FILE):
            self.create_setting_file()
        self.load_settings()

        self.screenWidth = self.width()
        self.screenHeight = self.height()

        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        self.layout = QHBoxLayout(self.centralWidget)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.image_labels = [QLabel(self) for _ in range(MAX_VIEW)]
        for i, label in enumerate(self.image_labels):
            label.setStyleSheet(BACK_COLORS[i])
            label.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(label)

        self.webpmovies = [None] * MAX_VIEW

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #31363b;
            }
            QStatusBar::item {
                border: none;
            }
        """)
        self.setStatusBar(self.status_bar)

        self.status_labels = [QLabel(self) for _ in range(MAX_VIEW)]
        default_texts = [f"slot {i+1}" for i in range(MAX_VIEW)]

        layout_statusbar_widget = QWidget(self)
        self.layout_statusbar = QHBoxLayout(layout_statusbar_widget)
        self.layout_statusbar.setContentsMargins(0, 0, 0, 0)

        for i, label in enumerate(self.status_labels):
            label.setText(default_texts[i])
            label.setStyleSheet("color: white; font-family: 'MS Gothic'; font-size: 11px;")
            label.setAlignment(Qt.AlignCenter)
            self.layout_statusbar.addWidget(label)

        self.status_bar.addPermanentWidget(layout_statusbar_widget, 1)

        self.set_split_count(self.visible_count, save=False)

        if os.path.exists("res/CompareViewer.ico"):
            self.setWindowIcon(QIcon("res/CompareViewer.ico"))

        self.setAcceptDrops(True)

    def appexit(self):
        if self.auto_timer.isActive():
            self.auto_timer.stop()
        if self.fullscreen:
            self.toggleFullscreen()
        self.close()

    def create_setting_file(self):
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_MOVE_TOP, "movetop.wav")
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_MOVE_END, "moveend.wav")
        pvsubfunc.write_value_to_config(SETTINGS_FILE, AUTO_INTERVAL, 4)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, VISIBLE_COUNT, MAX_VIEW)
        self.save_settings()

    def load_settings(self):
        self.soundMoveTop = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_MOVE_TOP)
        self.soundMoveEnd = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_MOVE_END)

        interval = pvsubfunc.read_value_from_config(SETTINGS_FILE, AUTO_INTERVAL)
        if interval is not None and isinstance(interval, int):
            self.auto_interval = max(1, interval)
        else:
            self.auto_interval = 4

        v_count = pvsubfunc.read_value_from_config(SETTINGS_FILE, VISIBLE_COUNT)
        if v_count is not None and isinstance(v_count, int):
            self.visible_count = max(1, min(MAX_VIEW, v_count))
        else:
            self.visible_count = MAX_VIEW

        geox = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_X)
        geoy = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_Y)
        geow = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_W)
        geoh = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_H)
        if any(val is None for val in [geox, geoy, geow, geoh]):
            self.setGeometry(0, 0, 1200, 600)
        else:
            self.setGeometry(geox, geoy, geow, geoh)

    def save_settings(self):
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_X, self.geometry().x())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_Y, self.geometry().y())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_W, self.geometry().width())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_H, self.geometry().height())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, AUTO_INTERVAL, self.auto_interval)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, VISIBLE_COUNT, self.visible_count)

    def set_split_count(self, count, save=True):
        if count < 1 or count > MAX_VIEW:
            return
        self.visible_count = count

        for i in range(MAX_VIEW):
            is_visible = i < self.visible_count
            self.image_labels[i].setVisible(is_visible)
            self.status_labels[i].setVisible(is_visible)

        if save:
            self.save_settings()

        self.update_image()

    # 現在のキー押下順序を反映したスロット配置マッピングを取得
    def get_current_mapping(self):
        mapping = list(range(MAX_VIEW))
        # アクティブなスワップ操作を順次適用（押し順ケア）
        for key in self.active_swap_keys:
            if key == Qt.Key_Z:
                mapping[0], mapping[1] = mapping[1], mapping[0]
            elif key == Qt.Key_X:
                mapping[1], mapping[2] = mapping[2], mapping[1]
            elif key == Qt.Key_C:
                mapping[2], mapping[3] = mapping[3], mapping[2]
            elif key == Qt.Key_V:
                mapping[3], mapping[4] = mapping[4], mapping[3]
            elif key == Qt.Key_B:
                mapping[4], mapping[5] = mapping[5], mapping[4]
        return mapping

    def toggle_auto_play(self):
        if self.auto_timer.isActive():
            self.auto_timer.stop()
        else:
            self.auto_timer.start(self.auto_interval * 1000)
        self.update_status_bar()

    def change_auto_interval(self, delta):
        self.auto_interval = max(1, self.auto_interval + delta)
        self.save_settings()
        if self.auto_timer.isActive():
            self.auto_timer.start(self.auto_interval * 1000)
        self.update_status_bar()

    def update_image(self):
        mapping = self.get_current_mapping()

        for slot_idx in range(self.visible_count):
            data_idx = mapping[slot_idx]
            label = self.image_labels[slot_idx]

            if self.image_paths[data_idx] and self.current_indices[data_idx] < len(self.image_paths[data_idx]):
                fname = self.image_paths[data_idx][self.current_indices[data_idx]]
                pixmap = QPixmap(fname)
                self.image_sizestr[data_idx] = f"{pixmap.width()}x{pixmap.height()}"
            else:
                pixmap = QPixmap()
                self.image_sizestr[data_idx] = ""

            imgsize = label.size()
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(imgsize, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                label.clear()

            if self.image_paths[data_idx]:
                fname = self.image_paths[data_idx][self.current_indices[data_idx]]
                if fname.lower().endswith(".webp"):
                    self.webpmovies[slot_idx] = QMovie(fname)
                    label.setMovie(self.webpmovies[slot_idx])
                    self.webpmovies[slot_idx].setScaledSize(self.get_fit_size(QImageReader(fname).size(), label.size()))
                    self.webpmovies[slot_idx].start()
                else:
                    self.webpmovies[slot_idx] = None
            else:
                self.webpmovies[slot_idx] = None

            # 背景色も画像（データ）と一緒に移動するように変更
            label.setStyleSheet(BACK_COLORS[data_idx])

        self.update_status_bar()

    def update_status_bar(self):
        mapping = self.get_current_mapping()

        for slot_idx in range(self.visible_count):
            data_idx = mapping[slot_idx]
            label = self.status_labels[slot_idx]
            if self.image_paths[data_idx]:
                imgpos = str(self.current_indices[data_idx] + 1).rjust(self.imagefiles_digits, " ")
                imgnum = str(len(self.image_paths[data_idx])).rjust(self.imagefiles_digits, " ")
                posinfo = f"[{imgpos}/{imgnum}] {self.image_sizestr[data_idx]}"
                fileinfo = os.path.basename(self.image_paths[data_idx][self.current_indices[data_idx]])
                label.setText(f"{posinfo} {fileinfo}")
            else:
                label.setText(f"slot {slot_idx+1}")

        valid_titles = [f"[{slot_idx+1}: {os.path.basename(self.image_paths[mapping[slot_idx]][self.current_indices[mapping[slot_idx]]])}]" for slot_idx in range(self.visible_count) if self.image_paths[mapping[slot_idx]]]
        base_title = " - ".join(valid_titles) if valid_titles else WINDOW_TITLE

        status_suffix = f" [Auto: {self.auto_interval}s {'ON' if self.auto_timer.isActive() else 'OFF'}]"
        self.setWindowTitle(base_title + status_suffix)
        self.update()

    def navigate_images(self, step):
        moved = False
        for i in range(MAX_VIEW):
            if self.image_paths[i]:
                self.current_indices[i] = (self.current_indices[i] + step) % len(self.image_paths[i])
                moved = True

        if not moved:
            return

        self.update_image()

        target = -1
        for i in range(MAX_VIEW):
            if self.image_paths[i]:
                target = i
                break

        if target != -1 and len(self.image_paths[target]) > 1:
            if self.current_indices[target] == 0 and step == 1:
                self.play_wave(self.soundMoveTop)
            elif self.current_indices[target] == (len(self.image_paths[target]) - 1) and step == -1:
                self.play_wave(self.soundMoveEnd)

    def play_wave(self, file_name):
        file_path = os.path.join(self.pydir, file_name).replace("\\", "/")
        if not os.path.isfile(file_path): return
        sound = QSound(file_path)
        sound.play()
        while sound.isFinished() is False:
            app.processEvents()

    def get_image_files(self, directory):
        files = [os.path.join(directory, f).replace("\\", "/") for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in SUPPORT_EXT]
        files = os_sorted(files)
        return files

    def get_slot_index_by_pos(self, pos: QPoint):
        width = self.width()
        if width <= 0 or self.visible_count <= 0:
            return 0
        slot_width = width / self.visible_count
        index = int(pos.x() // slot_width)
        return max(0, min(self.visible_count - 1, index))

    def toggleFitScreen(self):
        if self.fullscreen:
            return
        mapping = self.get_current_mapping()
        target = -1
        for slot_idx in range(self.visible_count):
            data_idx = mapping[slot_idx]
            if self.image_paths[data_idx]:
                target = data_idx
                break
        if target == -1:
            return

        if self.fitscreen < 0:
            self.fitscreen = 1
            self.screenWidth, self.screenHeight = self.width(), self.height()
            pixmap = QPixmap(self.image_paths[target][self.current_indices[target]])
            lw, lh = pixmap.width(), pixmap.height()
            correct_height = self.screenHeight - self.centralWidget.height()

            lw = lw * self.visible_count
            lw = max(lw, 400)
            lh += correct_height
            self.resize(lw, lh)
        else:
            self.fitscreen = -1
            self.resize(self.screenWidth, self.screenHeight)

    def toggleFullscreen(self):
        if self.fullscreen:
            self.showNormal()
            self.status_bar.show()
            self.setWindowFlags(self.windowFlags() & ~Qt.FramelessWindowHint)
        else:
            self.showFullScreen()
            self.status_bar.hide()
            self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.fullscreen = not self.fullscreen
        self.show()
        self.update_image()

    def get_fit_size(self, size_org, size_target):
        scaled_width = size_target.width()
        scaled_height = int(size_org.height() * (scaled_width / size_org.width()))
        if scaled_height > size_target.height():
            scaled_height = size_target.height()
            scaled_width = int(size_org.width() * (scaled_height / size_org.height()))
        return QSize(scaled_width, scaled_height)

    def keyPressEvent(self, event):
        keyid = event.key()
        if event.modifiers() & Qt.ControlModifier:
            if keyid in {Qt.Key_W}:
                self.appexit()
        elif keyid in {Qt.Key_D, Qt.Key_Right}:
            self.navigate_images(1)
        elif keyid in {Qt.Key_A, Qt.Key_Left}:
            self.navigate_images(-1)
        elif keyid == Qt.Key_2:
            self.set_split_count(2)
        elif keyid == Qt.Key_3:
            self.set_split_count(3)
        elif keyid == Qt.Key_4:
            self.set_split_count(4)
        elif keyid == Qt.Key_5:
            self.set_split_count(5)
        elif keyid == Qt.Key_6:
            self.set_split_count(6)
        # ZXCVBキー押下 (押し順ケア対応)
        elif keyid in {Qt.Key_Z, Qt.Key_X, Qt.Key_C, Qt.Key_V, Qt.Key_B} and not event.isAutoRepeat():
            if keyid not in self.active_swap_keys:
                self.active_swap_keys.append(keyid)
                self.update_image()
        # 下キーまたはSキー押下でZキーと同じ（slot1と2の入替）
        elif keyid in {Qt.Key_S, Qt.Key_Down} and not event.isAutoRepeat():
            if Qt.Key_Z not in self.active_swap_keys:
                self.active_swap_keys.append(Qt.Key_Z)
                self.update_image()
        elif keyid == Qt.Key_T:
            self.toggle_auto_play()
        elif keyid == Qt.Key_BracketLeft:
            self.change_auto_interval(-1)
        elif keyid == Qt.Key_BracketRight:
            self.change_auto_interval(1)
        elif keyid == Qt.Key_F:
            self.toggleFitScreen()
        elif keyid in {Qt.Key_Enter, Qt.Key_Return}:
            self.toggleFullscreen()
        elif keyid in {Qt.Key_Escape, Qt.Key_Q, Qt.Key_Slash, Qt.Key_Backslash}:
            self.appexit()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        keyid = event.key()
        if keyid in {Qt.Key_Z, Qt.Key_X, Qt.Key_C, Qt.Key_V, Qt.Key_B} and not event.isAutoRepeat():
            if keyid in self.active_swap_keys:
                self.active_swap_keys.remove(keyid)
                self.update_image()
        elif keyid in {Qt.Key_Down, Qt.Key_S} and not event.isAutoRepeat():
            if Qt.Key_Z in self.active_swap_keys:
                self.active_swap_keys.remove(Qt.Key_Z)
                self.update_image()
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        self.update_image()
        super().resizeEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        mapping = self.get_current_mapping()

        if len(urls) > 1:
            urls = urls[:self.visible_count]
            for slot_idx, url in enumerate(urls):
                if slot_idx >= self.visible_count: break
                data_idx = mapping[slot_idx]
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    if not any(file_path.lower().endswith(ext) for ext in SUPPORT_EXT):
                        continue
                    self.image_dirs[data_idx] = os.path.dirname(file_path)
                    self.image_paths[data_idx] = self.get_image_files(self.image_dirs[data_idx])
                    try:
                        self.current_indices[data_idx] = self.image_paths[data_idx].index(file_path)
                    except ValueError:
                        self.current_indices[data_idx] = 0
                elif os.path.isdir(file_path):
                    self.image_dirs[data_idx] = file_path
                    self.image_paths[data_idx] = self.get_image_files(self.image_dirs[data_idx])
                    self.current_indices[data_idx] = 0
        else:
            url = urls[0]
            file_path = url.toLocalFile()
            target_slot = self.get_slot_index_by_pos(self.mapFromGlobal(QCursor.pos()))
            data_idx = mapping[target_slot]

            if os.path.isfile(file_path):
                if any(file_path.lower().endswith(ext) for ext in SUPPORT_EXT):
                    self.image_dirs[data_idx] = os.path.dirname(file_path)
                    self.image_paths[data_idx] = self.get_image_files(self.image_dirs[data_idx])
                    try:
                        self.current_indices[data_idx] = self.image_paths[data_idx].index(file_path)
                    except ValueError:
                        self.current_indices[data_idx] = 0
            elif os.path.isdir(file_path):
                self.image_dirs[data_idx] = file_path
                self.image_paths[data_idx] = self.get_image_files(self.image_dirs[data_idx])
                self.current_indices[data_idx] = 0

        self.imagefiles_digits = 1
        for i in range(MAX_VIEW):
            if not self.image_paths[i]: continue
            digitslen = len(str(len(self.image_paths[i])))
            if self.imagefiles_digits < digitslen:
                self.imagefiles_digits = digitslen

        self.update_image()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.navigate_images(-1)
        else:
            self.navigate_images(1)
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_pos = event.globalPos()
        elif event.button() == Qt.RightButton:
            if Qt.Key_Z not in self.active_swap_keys:
                self.active_swap_keys.append(Qt.Key_Z)
                self.update_image()

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPos() - self.last_pos
            self.move(self.pos() + delta)
            self.last_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
        elif event.button() == Qt.RightButton:
            if Qt.Key_Z in self.active_swap_keys:
                self.active_swap_keys.remove(Qt.Key_Z)
                self.update_image()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggleFullscreen()
        super().mouseDoubleClickEvent(event)

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = CompareViewer()
    viewer.show()
    sys.exit(app.exec_())