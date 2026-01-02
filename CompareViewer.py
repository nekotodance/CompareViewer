import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QStatusBar, QHBoxLayout
from PyQt5.QtGui import QPixmap, QCursor, QIcon, QMovie, QImageReader
from PyQt5.QtCore import Qt, QEvent, QPoint, QSize
from PyQt5.QtMultimedia import QSound
import pvsubfunc

# アプリ名称
WINDOW_TITLE = "Compare Viewer 0.1.5"
# 設定ファイル
SETTINGS_FILE = "CompareViewer_settings.json"
# 設定ファイルのキー名
SOUND_MOVE_TOP = "sound-move-top"
SOUND_MOVE_END = "sound-move-end"
GEOMETRY_X = "geometry-x"
GEOMETRY_Y = "geometry-y"
GEOMETRY_W = "geometry-w"
GEOMETRY_H = "geometry-h"
SUPPORT_EXT = [".png", ".jpg", ".jpeg", ".webp"]
# dummy画像（片側のみしか表示されていない場合のウインドウサイズ変更対応）
DUMMY_IMAGES = ["dummy-left.jpg", "dummy-right.jpg"]
# 背景カラーも左右を入れ替えるように対応
BACK_COLORS = ["background-color: #222222;", "background-color: #111111;"]

class CompareViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # 変数
        self.image_paths = [None, None]
        self.image_dirs = [None, None]
        self.imagefiles_digits = 1      # ファイル総数の桁数
        self.current_indices = [0, 0]
        self.temp_order = [0, 1]        # 画像の左右入れ替え様
        self.soundMoveTop = ""
        self.soundMoveEnd = ""
        self.pydir = os.path.dirname(os.path.abspath(__file__))
        self.dragging = False           # 画像を移動するための変数
        self.last_pos = None
        self.fitscreen = -1
        self.fullscreen = False

        # ウインドウ
        self.setWindowTitle(WINDOW_TITLE)
        #self.setStyleSheet("background-color: black;")
        self.setGeometry(0, 0, 640, 640)
        self.setMinimumSize(640, 320)
        # ウインドウサイズを含め設定ロード処理
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

        # 画像表示用ラベル
        self.image_labels = [QLabel(self) for _ in range(2)]
        self.image_labels[0].setStyleSheet(BACK_COLORS[0])
        self.image_labels[1].setStyleSheet(BACK_COLORS[1])
        for label in self.image_labels:
            label.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(label)

        #webp再生用QMovie
        self.webpmovie = None   # 画像表示でwebpだった場合のプレイヤー

        # ステータスバー
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #31363b;
            }
            QStatusBar::item {
                border: none;               /* アイテム間のボーダー（白い縦棒の区切り）なし */
            }
        """)
        self.setStatusBar(self.status_bar)
        # ステータスバーラベル
        self.status_labels = [QLabel(self) for _ in range(2)]
        texts = ["left", "right"]
        for label, text in zip(self.status_labels, texts):
            label.setText(text)
            label.setStyleSheet("color: white; font-family: 'MS Gothic'; font-size: 12px;")
            label.setAlignment(Qt.AlignCenter)
        self.layout_statusbar_widget = QWidget()
        layout_statusbar = QHBoxLayout(self.layout_statusbar_widget)
        layout_statusbar.setContentsMargins(0, 0, 0, 0)
        layout_statusbar.addWidget(self.status_labels[0])
        layout_statusbar.addStretch(1)
        layout_statusbar.addWidget(self.status_labels[1])
        self.status_bar.addPermanentWidget(self.layout_statusbar_widget, 1)  # stretch factor = 1

        # アプリ左上のアイコンを設定
        self.setWindowIcon(QIcon("res/CompareViewer.ico"))

        # ドラッグ＆ドロップ有効化
        self.setAcceptDrops(True)

    #終了時処理
    def appexit(self):
        #全画面を解除してから終了（変な画面サイズが保存されてしまうため）
        if self.fullscreen:
            self.toggleFullscreen()
        self.close()

    # 設定ファイルの初期値作成
    def create_setting_file(self):
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_MOVE_TOP,  "movetop.wav")
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_MOVE_END,  "moveend.wav")
        self.save_settings()
    # 設定ファイルのロード
    def load_settings(self):
        self.soundMoveTop = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_MOVE_TOP)
        self.soundMoveEnd = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_MOVE_END)
        geox = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_X)
        geoy = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_Y)
        geow = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_W)
        geoh = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_H)
        if any(val is None for val in [geox, geoy, geow, geoh]):
            self.setGeometry(0, 0, 640, 640)
        else:
            self.setGeometry(geox, geoy, geow, geoh)    #位置とサイズ
    # 設定ファイルのセーブ
    def save_settings(self):
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_X, self.geometry().x())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_Y, self.geometry().y())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_W, self.geometry().width())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_H, self.geometry().height())

    # 画像の更新時処理（ロード時、サイズ変更時、左右入れ替え時）
    def update_image(self):
        for i, label_index in enumerate(self.temp_order):
            label = self.image_labels[label_index]

            if self.image_paths[i] and self.current_indices[i] < len(self.image_paths[i]):
                pixmap = QPixmap(self.image_paths[i][self.current_indices[i]])
            else:
                pixmap = QPixmap(DUMMY_IMAGES[i])
            imgsize = label.size()
            label.setPixmap(pixmap.scaled(imgsize, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            if self.image_paths[i]:
                fname = self.image_paths[i][self.current_indices[i]]
                if fname.lower().endswith(".webp"):
                    self.webpmovie = QMovie(fname)
                    label.setMovie(self.webpmovie)
                    self.webpmovie.setScaledSize(self.get_fit_size(QImageReader(fname).size(), label.size()))
                    self.webpmovie.start()
            else:
                self.webpmovie = None

            self.image_labels[i].setStyleSheet(BACK_COLORS[label_index])
        self.update_status_bar()

    # ステータスバーの更新
    def update_status_bar(self):
        paths = [self.image_paths[i][self.current_indices[i]] if self.image_paths[i] else "" for i in range(2)]
        deftexts = ["left", "right"]
        posinfos = ["", ""]
        for i, label_index in enumerate(self.temp_order):
            label = self.status_labels[label_index]
            if paths[i]:
                imgpos = str(self.current_indices[i] + 1).rjust(self.imagefiles_digits, " ")
                imgnum = str(len(self.image_paths[i])).rjust(self.imagefiles_digits, " ")
                posinfo = f"[{imgpos}/{imgnum}]"
                posinfos[label_index] = posinfo
                fileinfo = f"{self.getParentDir(paths[i])}/{os.path.basename(paths[i])}"
                label.setText(f"{posinfo} {fileinfo}")
            else:
                label.setText(deftexts[i])

        # ファイルのインデックスをWindowタイトル部分に表示
        self.setWindowTitle(f"{posinfos[0]}, {posinfos[1]}")
        self.update()

    # 親ディレクトリ名の取得
    def getParentDir(self, path):
        return os.path.basename(os.path.dirname(path))

    # 前後の画像処理
    def navigate_images(self, step):
        for i in range(2):
            if self.image_paths[i]:
                self.current_indices[i] = (self.current_indices[i] + step) % len(self.image_paths[i])
        self.update_image()
        #ループ時サウンド（左優先、左に画像が無いもしくは1ファイルのみ場合のみ右で判定）
        target = 0
        if not self.image_paths[0]:
            target = 1
        elif len(self.image_paths[0]) == 1:
            target = 1
        if self.image_paths[target]:
            if len(self.image_paths[target]) > 1:
                if self.current_indices[target] == 0 and step == 1:
                    self.play_wave(self.soundMoveTop)
                if self.current_indices[target] == (len(self.image_paths[target]) - 1) and step == -1:
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
        return [os.path.join(directory, f).replace("\\", "/") for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in SUPPORT_EXT]

    # 画像の左右入れ替え
    def swap_image(self, isSwap):
        if isSwap:
            self.temp_order = [1, 0]
        else:
            self.temp_order = [0, 1]
        pvsubfunc.dbgprint(f"[DBG] update_image - start")
        self.update_image()
        pvsubfunc.dbgprint(f"[DBG] update_image - end")

    # 現在のカーソル位置（ウインドウ内の相対位置）を取得
    def get_mouse_pos(self):
        pos_global = QCursor.pos()
        pos_local = self.mapFromGlobal(pos_global)
        return pos_local
    # カーソル位置がどちらの画像上かチェック
    def is_left_image_pos(self, pos: QPoint):
        center = self.width() // 2
        mposx = pos.x()
        if center < mposx:
            return False
        return True

    #画像サイズ変更トグル
    def toggleFitScreen(self, scale):
        if self.fullscreen:
            return  # 全画面表示中は無効
        target = -1
        if self.image_paths[0]:
            target = 0  # 左に画像あり
        elif self.image_paths[1]:
            target = 1  # 右に画像あり
        else:
            return  # どちらにも画像がない場合は無効

        if self.fitscreen < 0:
            #通常モードからFitモードへ
            self.fitscreen = scale
            #現在のウインドウサイズを退避
            self.screenWidth, self.screenHeight = self.width(), self.height()
            pixmap = QPixmap(self.image_paths[target][self.current_indices[target]])
            lw, lh = pixmap.width(), pixmap.height()  # 画像のサイズ
            # Widghetの領域とウインドウの領域の差分を算出
            correct_height = self.screenHeight - self.centralWidget.height()
            if self.fitscreen == 0:
                lw = lw
                lh = lh // 2
            elif self.fitscreen == 1:
                lw = lw * 2
            elif self.fitscreen == 2:
                lw = lw * 4
                lh = lh * 2

            lh += correct_height        # Widghetの領域とウインドウの領域の差分を追加
            self.resize(lw, lh)
        else:
            #Fitモードから通常モードへ
            self.fitscreen = -1
            #元のウインドウサイズに復帰
            self.resize(self.screenWidth, self.screenHeight)

    #全画面切り替えトグル
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
        self.show()     #ウィジェットが表示/非表示などを切り替える場合など
        self.update_image()

    # webpを再生中なら停止する
    def stop_WEbpMovie(self):
        if self.webpmovie != None:
            self.webpmovie.stop()
            self.webpmovie = None

    # 元のサイズをターゲットサイズにフィットさせた場合のサイズを取得
    def get_fit_size(self, size_org, size_target):
        scaled_width = size_target.width()
        scaled_height = int(size_org.height() * (scaled_width / size_org.width()))
        if scaled_height > size_target.height():
            scaled_height = size_target.height()
            scaled_width = int(size_org.width() * (scaled_height / size_org.height()))
        return QSize(scaled_width,scaled_height)

    #========================================
    #= キーイベント処理
    #= https://doc.qt.io/qt-5/qt.html#Key-enum
    #========================================
    def keyPressEvent(self, event):
        keyid = event.key()
        pvsubfunc.dbgprint(f"[DBG] key press id : {keyid}")
        #Ctrlキー併用は別で処理する
        if event.modifiers() & Qt.ControlModifier:
            if keyid in {Qt.Key_W}:
                self.appexit()
        # 次のイメージへ
        elif keyid in {Qt.Key_D, Qt.Key_Right}:
            self.navigate_images(1)
        # 前のイメージへ
        elif keyid in {Qt.Key_A, Qt.Key_Left}:
            self.navigate_images(-1)
        # 左右入れ替え
        elif keyid in {Qt.Key_S, Qt.Key_Down}:
            self.swap_image(True)
        # 1/2倍表示
        if keyid == Qt.Key_0:
            self.toggleFitScreen(0)
        # 等倍表示
        elif keyid in {Qt.Key_1, Qt.Key_F}:
            self.toggleFitScreen(1)
        # 2倍表示
        elif keyid == Qt.Key_2:
            self.toggleFitScreen(2)
        # 全画面切り替え
        elif keyid in {Qt.Key_Enter, Qt.Key_Return}:
            self.toggleFullscreen()
        # 終了
        elif keyid in {Qt.Key_Escape, Qt.Key_Q, Qt.Key_Slash, Qt.Key_Backslash}:
            self.appexit()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        keyid = event.key()
        pvsubfunc.dbgprint(f"[DBG] key release id : {keyid}")
        # 左右入れ替え
        if keyid in {Qt.Key_S, Qt.Key_Down}:
            self.swap_image(False)
        super().keyPressEvent(event)

    #========================================
    #= イベント処理
    #========================================
    # ウインドウサイズ変更
    def resizeEvent(self, event):
        self.update_image()
        super().resizeEvent(event)

    # ドラッグエンター
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    # ドラッグドロップ
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        # ドロップが3つ以上の場合2つめまでだけに補正
        if len(urls) > 2:
            urls = urls[:2]
        # ドロップが1つのファイルもしくはフォルダで右にドロップされた場合は、右側へ反映させる
        if len(urls) == 1:
            if not self.is_left_image_pos(self.get_mouse_pos()):
                urls = [None, urls[0]]

        for i, url in enumerate(urls):
            if not url: continue
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                if not any(file_path.lower().endswith(ext) for ext in SUPPORT_EXT):
                    continue
                self.image_dirs[i] = os.path.dirname(file_path)
                self.image_paths[i] = self.get_image_files(self.image_dirs[i])
                self.current_indices[i] = self.image_paths[i].index(file_path)
            elif os.path.isdir(file_path):
                self.image_dirs[i] = file_path
                self.image_paths[i] = self.get_image_files(self.image_dirs[i])
                self.current_indices[i] = 0
        self.imagefiles_digits = 1
        for i in range(2):
            if not self.image_paths[i]: continue
            digitslen = len(str(len(self.image_paths[i])))
            if self.imagefiles_digits < digitslen:
                self.imagefiles_digits = digitslen
        self.update_image()

    # ホイールで前後ファイルに移動
    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.navigate_images(-1)
        else:
            self.navigate_images(1)
        super().wheelEvent(event)
    # マウスボタンプレス
    def mousePressEvent(self, event):
        pvsubfunc.dbgprint(f"[DBG] mouse button : {event.button()}")
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_pos = event.globalPos()
        elif event.button() == Qt.RightButton:
            self.swap_image(True)
    # マウス移動
    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPos() - self.last_pos
            self.move(self.pos() + delta)
            self.last_pos = event.globalPos()
    # マウスボタンリリース
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
        elif event.button() == Qt.RightButton:
            self.swap_image(False)
    #ダブルクリック時に全画面切り替え
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggleFullscreen()
        super().mouseDoubleClickEvent(event)

    # アプリ終了時
    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = CompareViewer()
    viewer.show()
    sys.exit(app.exec_())
