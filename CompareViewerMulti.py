import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QStatusBar, QHBoxLayout
from PyQt5.QtGui import QPixmap, QCursor, QIcon, QMovie, QImageReader
from PyQt5.QtCore import Qt, QPoint, QSize, QTimer
from PyQt5.QtMultimedia import QSound
import pvsubfunc
from natsort import os_sorted

# アプリ名称
WINDOW_TITLE = "Compare Viewer Dynamic-Split 0.5.0"
# 設定ファイル
SETTINGS_FILE = "CompareViewer5_settings.json"
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
MAX_VIEW = 5

# 背景カラーをスロットごとに変更
BACK_COLORS = [
    "background-color: #222222;",
    "background-color: #181818;",
    "background-color: #141414;",
    "background-color: #101010;",
    "background-color: #0b0b0b;"
]

class CompareViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.visible_count = MAX_VIEW  # デフォルト（設定ロード前）
        self.auto_interval = 4         # デフォルト（設定ロード前）
        
        # 自動ページ送り用タイマー
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(lambda: self.navigate_images(1))
        
        self.init_ui()

    def init_ui(self):
        # 変数（5つ分）
        self.image_paths = [None] * MAX_VIEW
        self.image_dirs = [None] * MAX_VIEW
        self.image_sizestr = [""] * MAX_VIEW
        self.imagefiles_digits = 1      # ファイル総数の桁数
        self.current_indices = [0] * MAX_VIEW
        self.soundMoveTop = ""
        self.soundMoveEnd = ""
        self.pydir = os.path.dirname(os.path.abspath(__file__))
        self.dragging = False           # 画像を移動するための変数
        self.last_pos = None
        self.fitscreen = -1
        self.fullscreen = False

        # ウインドウ
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(0, 0, 1200, 600)
        self.setMinimumSize(400, 320)
        
        # 設定ファイルの初期値作成 & ロード
        if not os.path.exists(SETTINGS_FILE):
            self.create_setting_file()
        self.load_settings()
        
        # 起動時のスクリーンサイズ退避
        self.screenWidth = self.width()
        self.screenHeight = self.height()

        # メインウィジェットとレイアウト
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        self.layout = QHBoxLayout(self.centralWidget)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # 画像表示用ラベル（5個）
        self.image_labels = [QLabel(self) for _ in range(MAX_VIEW)]
        for i, label in enumerate(self.image_labels):
            label.setStyleSheet(BACK_COLORS[i])
            label.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(label)

        # webp再生用QMovie
        self.webpmovies = [None] * MAX_VIEW

        # ステータスバー
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
        
        # ステータスバーラベル（5個分のレイアウト）
        self.status_labels = [QLabel(self) for _ in range(MAX_VIEW)]
        default_texts = [f"slot {i+1}" for i in range(MAX_VIEW)]
        
        layout_statusbar_widget = QWidget()
        self.layout_statusbar = QHBoxLayout(layout_statusbar_widget)
        self.layout_statusbar.setContentsMargins(0, 0, 0, 0)
        
        for i, label in enumerate(self.status_labels):
            label.setText(default_texts[i])
            label.setStyleSheet("color: white; font-family: 'MS Gothic'; font-size: 11px;")
            label.setAlignment(Qt.AlignCenter)
            self.layout_statusbar.addWidget(label)

        self.status_bar.addPermanentWidget(layout_statusbar_widget, 1)

        # 読み込んだ設定値に基づいてスロットの表示状態を初期反映
        self.set_split_count(self.visible_count, save=False)

        # アプリ左上のアイコンを設定
        if os.path.exists("res/CompareViewer.ico"):
            self.setWindowIcon(QIcon("res/CompareViewer.ico"))

        # ドラッグ＆ドロップ有効化
        self.setAcceptDrops(True)

    # 終了時処理
    def appexit(self):
        if self.auto_timer.isActive():
            self.auto_timer.stop()
        if self.fullscreen:
            self.toggleFullscreen()
        self.close()

    # 設定ファイルの初期値作成
    def create_setting_file(self):
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_MOVE_TOP, "movetop.wav")
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_MOVE_END, "moveend.wav")
        pvsubfunc.write_value_to_config(SETTINGS_FILE, AUTO_INTERVAL, 4)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, VISIBLE_COUNT, MAX_VIEW)
        self.save_settings()

    # 設定ファイルのロード
    def load_settings(self):
        self.soundMoveTop = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_MOVE_TOP)
        self.soundMoveEnd = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_MOVE_END)
        
        # 自動送り秒数のロード
        interval = pvsubfunc.read_value_from_config(SETTINGS_FILE, AUTO_INTERVAL)
        if interval is not None and isinstance(interval, int):
            self.auto_interval = max(1, interval)
        else:
            self.auto_interval = 4

        # 分割数のロード
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

    # 設定ファイルのセーブ
    def save_settings(self):
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_X, self.geometry().x())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_Y, self.geometry().y())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_W, self.geometry().width())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_H, self.geometry().height())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, AUTO_INTERVAL, self.auto_interval)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, VISIBLE_COUNT, self.visible_count)

    # 動的分割数の変更
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

    # 2画像比較時の左右入替
    def swap_images_2way(self):
        if self.visible_count == 2:
            self.image_paths[0], self.image_paths[1] = self.image_paths[1], self.image_paths[0]
            self.image_dirs[0], self.image_dirs[1] = self.image_dirs[1], self.image_dirs[0]
            self.image_sizestr[0], self.image_sizestr[1] = self.image_sizestr[1], self.image_sizestr[0]
            self.current_indices[0], self.current_indices[1] = self.current_indices[1], self.current_indices[0]
            self.webpmovies[0], self.webpmovies[1] = self.webpmovies[1], self.webpmovies[0]
            self.update_image()

    # 自動ページ送りのトグル
    def toggle_auto_play(self):
        if self.auto_timer.isActive():
            self.auto_timer.stop()
        else:
            self.auto_timer.start(self.auto_interval * 1000)
        self.update_status_bar()

    # 自動送り秒数の変更 ([ と ] キー)
    def change_auto_interval(self, delta):
        self.auto_interval = max(1, self.auto_interval + delta)
        self.save_settings()
        if self.auto_timer.isActive():
            self.auto_timer.start(self.auto_interval * 1000)
        self.update_status_bar()

    # 画像の更新時処理
    def update_image(self):
        for i in range(self.visible_count):
            label = self.image_labels[i]

            if self.image_paths[i] and self.current_indices[i] < len(self.image_paths[i]):
                fname = self.image_paths[i][self.current_indices[i]]
                pixmap = QPixmap(fname)
                self.image_sizestr[i] = f"{pixmap.width()}x{pixmap.height()}"
            else:
                pixmap = QPixmap()
                self.image_sizestr[i] = ""

            imgsize = label.size()
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(imgsize, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                label.clear()

            # webp動画対応
            if self.image_paths[i]:
                fname = self.image_paths[i][self.current_indices[i]]
                if fname.lower().endswith(".webp"):
                    self.webpmovies[i] = QMovie(fname)
                    label.setMovie(self.webpmovies[i])
                    self.webpmovies[i].setScaledSize(self.get_fit_size(QImageReader(fname).size(), label.size()))
                    self.webpmovies[i].start()
                else:
                    self.webpmovies[i] = None
            else:
                self.webpmovies[i] = None

            label.setStyleSheet(BACK_COLORS[i])
        
        self.update_status_bar()

    # ステータスバーの更新
    def update_status_bar(self):
        for i in range(self.visible_count):
            label = self.status_labels[i]
            if self.image_paths[i]:
                imgpos = str(self.current_indices[i] + 1).rjust(self.imagefiles_digits, " ")
                imgnum = str(len(self.image_paths[i])).rjust(self.imagefiles_digits, " ")
                posinfo = f"[{imgpos}/{imgnum}] {self.image_sizestr[i]}"
                fileinfo = os.path.basename(self.image_paths[i][self.current_indices[i]])
                label.setText(f"{posinfo} {fileinfo}")
            else:
                label.setText(f"slot {i+1}")

        # ウィンドウタイトルにファイル情報と自動送り秒数・状態を表示
        valid_titles = [f"[{i+1}: {os.path.basename(self.image_paths[i][self.current_indices[i]])}]" for i in range(self.visible_count) if self.image_paths[i]]
        base_title = " - ".join(valid_titles) if valid_titles else WINDOW_TITLE
        
        status_suffix = f" [Auto: {self.auto_interval}s {'ON' if self.auto_timer.isActive() else 'OFF'}]"
        self.setWindowTitle(base_title + status_suffix)
        self.update()

    # 前後の画像へ移動（表示中のスロットのみ対象）
    def navigate_images(self, step):
        moved = False
        for i in range(self.visible_count):
            if self.image_paths[i]:
                self.current_indices[i] = (self.current_indices[i] + step) % len(self.image_paths[i])
                moved = True
        
        if not moved:
            return

        self.update_image()

        # ループ時サウンド判定
        target = -1
        for i in range(self.visible_count):
            if self.image_paths[i]:
                target = i
                break
        
        if target != -1 and len(self.image_paths[target]) > 1:
            if self.current_indices[target] == 0 and step == 1:
                self.play_wave(self.soundMoveTop)
            elif self.current_indices[target] == (len(self.image_paths[target]) - 1) and step == -1:
                self.play_wave(self.soundMoveEnd)

    # wavファイルの再生
    def play_wave(self, file_name):
        file_path = os.path.join(self.pydir, file_name).replace("\\", "/")
        if not os.path.isfile(file_path): return
        sound = QSound(file_path)
        sound.play()
        while sound.isFinished() is False:
            app.processEvents()

    # 画像ファイルのリスト作成
    def get_image_files(self, directory):
        files = [os.path.join(directory, f).replace("\\", "/") for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in SUPPORT_EXT]
        files = os_sorted(files)
        return files

    # マウスカーソル位置（X座標割合）からドロップ先のスロット番号を算出
    def get_slot_index_by_pos(self, pos: QPoint):
        width = self.width()
        if width <= 0 or self.visible_count <= 0:
            return 0
        slot_width = width / self.visible_count
        index = int(pos.x() // slot_width)
        return max(0, min(self.visible_count - 1, index))

    # 画像サイズ等倍トグル (Key_F 用)
    def toggleFitScreen(self):
        if self.fullscreen:
            return
        target = -1
        for i in range(self.visible_count):
            if self.image_paths[i]:
                target = i
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

    # 全画面切り替えトグル
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

    # 元のサイズをターゲットサイズにフィットさせた場合のサイズを取得
    def get_fit_size(self, size_org, size_target):
        scaled_width = size_target.width()
        scaled_height = int(size_org.height() * (scaled_width / size_org.width()))
        if scaled_height > size_target.height():
            scaled_height = size_target.height()
            scaled_width = int(size_org.width() * (scaled_height / size_org.height()))
        return QSize(scaled_width, scaled_height)

    #========================================
    #= キーイベント処理
    #========================================
    def keyPressEvent(self, event):
        keyid = event.key()
        if event.modifiers() & Qt.ControlModifier:
            if keyid in {Qt.Key_W}:
                self.appexit()
        elif keyid in {Qt.Key_D, Qt.Key_Right}:
            self.navigate_images(1)
        elif keyid in {Qt.Key_A, Qt.Key_Left}:
            self.navigate_images(-1)
        # 動的分割切り替え (2〜5キー)
        elif keyid == Qt.Key_2:
            self.set_split_count(2)
        elif keyid == Qt.Key_3:
            self.set_split_count(3)
        elif keyid == Qt.Key_4:
            self.set_split_count(4)
        elif keyid == Qt.Key_5:
            self.set_split_count(5)
        # 2分割時のみSキー押下で左右入替（長押し対応、オートリピート無視）
        elif keyid == Qt.Key_S and not event.isAutoRepeat():
            self.swap_images_2way()
        # 自動ページ送り開始・停止 (Tキー)
        elif keyid == Qt.Key_T:
            self.toggle_auto_play()
        # 秒数変更 ([、] キー)
        elif keyid == Qt.Key_BracketLeft:  # [ キー
            self.change_auto_interval(-1)
        elif keyid == Qt.Key_BracketRight: # ] キー
            self.change_auto_interval(1)
        # 等倍表示トグル (Fキー)
        elif keyid == Qt.Key_F:
            self.toggleFitScreen()
        elif keyid in {Qt.Key_Enter, Qt.Key_Return}:
            self.toggleFullscreen()
        elif keyid in {Qt.Key_Escape, Qt.Key_Q, Qt.Key_Slash, Qt.Key_Backslash}:
            self.appexit()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        keyid = event.key()
        # 2分割時のみSキーを離したときに入れ替えをもとに戻す（オートリピート無視）
        if keyid == Qt.Key_S and not event.isAutoRepeat():
            self.swap_images_2way()
        super().keyPressEvent(event)

    #========================================
    #= イベント処理
    #========================================
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
        
        # 複数ファイルをドロップした場合、現在の分割数分まで割り当て
        if len(urls) > 1:
            urls = urls[:self.visible_count]
            for i, url in enumerate(urls):
                if i >= self.visible_count: break
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    if not any(file_path.lower().endswith(ext) for ext in SUPPORT_EXT):
                        continue
                    self.image_dirs[i] = os.path.dirname(file_path)
                    self.image_paths[i] = self.get_image_files(self.image_dirs[i])
                    try:
                        self.current_indices[i] = self.image_paths[i].index(file_path)
                    except ValueError:
                        self.current_indices[i] = 0
                elif os.path.isdir(file_path):
                    self.image_dirs[i] = file_path
                    self.image_paths[i] = self.get_image_files(self.image_dirs[i])
                    self.current_indices[i] = 0
        else:
            # 1ファイルのみドロップされた場合、カーソル位置のスロットに割り当て
            url = urls[0]
            file_path = url.toLocalFile()
            target_slot = self.get_slot_index_by_pos(self.mapFromGlobal(QCursor.pos()))
            
            if os.path.isfile(file_path):
                if any(file_path.lower().endswith(ext) for ext in SUPPORT_EXT):
                    self.image_dirs[target_slot] = os.path.dirname(file_path)
                    self.image_paths[target_slot] = self.get_image_files(self.image_dirs[target_slot])
                    try:
                        self.current_indices[target_slot] = self.image_paths[target_slot].index(file_path)
                    except ValueError:
                        self.current_indices[target_slot] = 0
            elif os.path.isdir(file_path):
                self.image_dirs[target_slot] = file_path
                self.image_paths[target_slot] = self.get_image_files(self.image_dirs[target_slot])
                self.current_indices[target_slot] = 0

        # 桁数調整
        self.imagefiles_digits = 1
        for i in range(self.visible_count):
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
            self.swap_images_2way()

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPos() - self.last_pos
            self.move(self.pos() + delta)
            self.last_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
        elif event.button() == Qt.RightButton:
            self.swap_images_2way()

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